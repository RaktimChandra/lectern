"""Runs the seven steps, saving the lesson after each one.

Because every step reads only what earlier steps stored on the lesson, a run
can start from any step. A failure stops the run, records a readable message
on that step and leaves everything before it intact, so "Retry this step"
loses nothing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from ..config import Settings
from ..events import EventBroker
from ..llm.base import LLMClient, LLMError
from ..models import STEP_ORDER, Lesson, LogLine, StepName, utcnow
from ..research.collector import ResearchToolkit
from ..store import LessonStore
from . import qc_facts, qc_instruction, steps
from .context import StepContext, StepError

log = logging.getLogger("lectern.runner")

StepFn = Callable[[StepContext], Awaitable[str]]

STEP_FUNCTIONS: dict[StepName, StepFn] = {
    StepName.analyze: steps.analyze,
    StepName.plan_research: steps.plan_research,
    StepName.research: steps.research,
    StepName.outline: steps.outline,
    StepName.draft: steps.draft,
    StepName.qc_facts: qc_facts.run,
    StepName.qc_instruction: qc_instruction.run,
}

MAX_LOG_LINES = 300

ModelFactory = Callable[[], tuple[LLMClient | None, LLMClient | None]]
ToolkitFactory = Callable[[], ResearchToolkit]


class Runner:
    def __init__(self, store: LessonStore, broker: EventBroker, settings: Settings,
                 models: ModelFactory, toolkit: ToolkitFactory):
        self.store = store
        self.broker = broker
        self.settings = settings
        self.models = models
        self.toolkit = toolkit
        self._tasks: dict[str, asyncio.Task] = {}

    def is_running(self, lesson_id: str) -> bool:
        task = self._tasks.get(lesson_id)
        return bool(task and not task.done())

    def start(self, lesson: Lesson, steps_to_run: list[StepName]) -> None:
        """Mark steps pending and run them in the background."""
        for name in steps_to_run:
            state = lesson.step(name)
            state.status, state.error, state.detail = "pending", None, ""
            state.started_at = state.finished_at = None
        lesson.running = True
        self.store.save(lesson)
        self._publish_lesson(lesson)
        task = asyncio.create_task(self._run(lesson.id, steps_to_run))
        self._tasks[lesson.id] = task

    def start_from(self, lesson: Lesson, from_step: StepName | None) -> None:
        if from_step is None:
            from_step = next((s.name for s in lesson.steps if s.status in ("failed", "pending")), STEP_ORDER[0])
        start = STEP_ORDER.index(from_step)
        self.start(lesson, STEP_ORDER[start:])

    async def wait(self, lesson_id: str) -> None:
        task = self._tasks.get(lesson_id)
        if task:
            await task

    async def _run(self, lesson_id: str, names: list[StepName]) -> None:
        writer, reviewer = self.models()
        toolkit = self.toolkit()
        for name in names:
            async with self.store.lock_for(lesson_id):
                lesson = self.store.get(lesson_id)
                if lesson is None:
                    return
                state = lesson.step(name)
                state.status, state.started_at, state.error = "running", utcnow(), None
                state.attempts += 1
                self.store.save(lesson)
            self.broker.publish(lesson_id, "step", state.model_dump(mode="json"))

            ctx = StepContext(lesson=lesson, settings=self.settings, writer=writer, reviewer=reviewer,
                              toolkit=toolkit, log=self._logger(lesson, name))
            try:
                detail = await STEP_FUNCTIONS[name](ctx)
            except (StepError, LLMError) as exc:
                await self._fail(lesson, name, str(exc))
                return
            except Exception as exc:  # unexpected: record it, keep the server alive
                log.exception("step %s failed", name.value)
                await self._fail(lesson, name, f"Unexpected error ({type(exc).__name__}): {exc}. Retry this step.")
                return

            async with self.store.lock_for(lesson_id):
                fresh = self.store.get(lesson_id)
                if fresh is not None:
                    lesson = merge_concurrent(lesson, fresh, name)
                state = lesson.step(name)
                state.status, state.finished_at, state.detail = "done", utcnow(), detail
                self.store.save(lesson)
            self.broker.publish(lesson_id, "step", state.model_dump(mode="json"))
            self._publish_lesson(lesson)

        async with self.store.lock_for(lesson_id):
            lesson = self.store.get(lesson_id)
            if lesson:
                lesson.running = False
                self.store.save(lesson)
                self._publish_lesson(lesson)

    async def _fail(self, lesson: Lesson, name: StepName, message: str) -> None:
        async with self.store.lock_for(lesson.id):
            fresh = self.store.get(lesson.id)
            if fresh is not None:
                fresh.log = lesson.log  # keep this run's log lines; keep any edits saved meanwhile
                fresh.research_log = lesson.research_log  # shows which searches failed
                lesson = fresh
            state = lesson.step(name)
            state.status, state.finished_at, state.error = "failed", utcnow(), message
            lesson.running = False
            lesson.log.append(LogLine(step=name, level="error", message=message))
            self.store.save(lesson)
        self.broker.publish(lesson.id, "step", state.model_dump(mode="json"))
        self.broker.publish(lesson.id, "log", {"step": name.value, "level": "error", "message": message})
        self._publish_lesson(lesson)

    def _logger(self, lesson: Lesson, name: StepName):
        async def write(message: str, level: str = "info") -> None:
            lesson.log.append(LogLine(step=name, level=level, message=message))
            del lesson.log[:-MAX_LOG_LINES]
            self.broker.publish(lesson.id, "log", {"step": name.value, "level": level, "message": message})
        return write

    def _publish_lesson(self, lesson: Lesson) -> None:
        self.broker.publish(lesson.id, "lesson", {"version": lesson.version_number, "running": lesson.running})


def merge_concurrent(worked: Lesson, fresh: Lesson, name: StepName) -> Lesson:
    """Combine a step's result with changes the instructor saved while the step was running.

    Each step owns a few fields (a report, a new version, or the research and
    planning outputs). Only those are carried over; the instructor's edits,
    dismissals and versions in the stored copy are always kept.
    """
    if name == StepName.qc_facts:
        fresh.fact_report = worked.fact_report
    elif name == StepName.qc_instruction:
        fresh.instruction_report = worked.instruction_report
    elif name == StepName.draft:
        new = worked.versions[-1]
        new.number = fresh.version_number + 1
        fresh.versions.append(new)
    else:
        # Generation steps: carry over only what the step produces.
        fresh.analysis = worked.analysis
        fresh.research_plan = worked.research_plan
        fresh.sources = worked.sources
        fresh.research_log = worked.research_log
        fresh.outline = worked.outline
    fresh.log = worked.log
    fresh.steps = worked.steps
    return fresh


def recover_interrupted(store: LessonStore) -> int:
    """On startup, any step still marked running was interrupted by a restart."""
    count = 0
    for lesson in store.list():
        changed = False
        for state in lesson.steps:
            if state.status == "running":
                state.status, state.error = "failed", "Lectern stopped while this step was running. Retry this step."
                changed = True
        if changed or lesson.running:
            lesson.running = False
            store.save(lesson)
            count += 1
    return count
