"""HTTP API. All routes live under /api."""

from __future__ import annotations

import asyncio
import json
import secrets

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import exporters
from .llm.base import LLMError
from .llm.providers import resolved_model
from .preflight import run_preflight
from .models import STEP_LABELS, Lesson, LessonRequest, StepName
from .pipeline import fixes
from .pipeline.context import StepContext, StepError
from .research.passages import chunk

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def services(request: Request):
    return request.app.state.services


def get_lesson(request: Request, lesson_id: str) -> Lesson:
    lesson = services(request).store.get(lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found.")
    return lesson


def serialize(lesson: Lesson) -> dict:
    data = lesson.model_dump(mode="json")
    for source in data["sources"]:
        source["has_full_text"] = len(source.pop("text", "") or "") > 400
    data["version"] = lesson.version_number
    data["step_labels"] = {k.value: v for k, v in STEP_LABELS.items()}
    data["versions"] = [
        {"number": v["number"], "created_at": v["created_at"], "reason": v["reason"]} for v in data["versions"]
    ]
    data["content"] = lesson.current.content.model_dump(mode="json") if lesson.current else None
    return data


def summary(lesson: Lesson) -> dict:
    failed = next((s for s in lesson.steps if s.status == "failed"), None)
    status = "running" if lesson.running else ("failed" if failed else ("ready" if lesson.current else "pending"))
    return {
        "id": lesson.id,
        "title": lesson.request.title,
        "objective": lesson.request.objective,
        "created_at": lesson.created_at,
        "updated_at": lesson.updated_at,
        "status": status,
        "version": lesson.version_number,
        "accuracy_score": lesson.fact_report.accuracy_score if lesson.fact_report else None,
        "quality_score": lesson.instruction_report.quality_score if lesson.instruction_report else None,
    }


def step_context(request: Request, lesson: Lesson) -> StepContext:
    svc = services(request)
    writer, reviewer = svc.models()

    async def log(message: str, level: str = "info") -> None:
        svc.broker.publish(lesson.id, "log", {"step": None, "level": level, "message": message})

    return StepContext(lesson=lesson, settings=svc.settings, writer=writer, reviewer=reviewer,
                       toolkit=svc.toolkit(), log=log)


def ensure_idle(request: Request, lesson: Lesson) -> None:
    if services(request).runner.is_running(lesson.id):
        raise HTTPException(409, "This lesson is still being generated or checked. Wait for the current step to finish.")


# ---------------------------------------------------------------------------
# Health and lessons
# ---------------------------------------------------------------------------


@router.get("/health")
def health(request: Request) -> dict:
    status = services(request).settings.public_status()
    # Show the model actually in use if discovery replaced a retired default.
    for role in ("writer", "reviewer"):
        if status.get(role):
            status[role]["model"] = resolved_model(status[role]["provider"], status[role]["model"])
    return status


@router.post("/preflight")
async def preflight(request: Request) -> dict:
    """Send one tiny real request to each configured service and report what works."""
    svc = services(request)
    try:
        writer, reviewer = svc.models()
    except LLMError as exc:
        return {"ok": False, "checks": [{"name": "Writer model", "role": "required", "ok": False, "ms": 0, "detail": str(exc)}]}
    checks = await run_preflight(writer, reviewer, svc.toolkit())
    ok = all(c["ok"] for c in checks if c["role"] == "required")
    return {"ok": ok, "checks": checks}


@router.get("/lessons")
def list_lessons(request: Request) -> list[dict]:
    return [summary(l) for l in services(request).store.list()]


@router.post("/lessons", status_code=201)
async def create_lesson(request: Request, body: LessonRequest) -> dict:
    svc = services(request)
    lesson = Lesson(id=secrets.token_urlsafe(6).replace("-", "x").replace("_", "y"), request=body)
    svc.store.save(lesson)
    svc.runner.start_from(lesson, StepName.analyze)
    return serialize(svc.store.get(lesson.id) or lesson)


@router.get("/lessons/{lesson_id}")
def read_lesson(request: Request, lesson_id: str) -> dict:
    return serialize(get_lesson(request, lesson_id))


@router.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(request: Request, lesson_id: str) -> Response:
    lesson = get_lesson(request, lesson_id)
    ensure_idle(request, lesson)
    services(request).store.delete(lesson_id)
    return Response(status_code=204)


class RunBody(BaseModel):
    from_step: StepName | None = None


@router.post("/lessons/{lesson_id}/run", status_code=202)
async def run(request: Request, lesson_id: str, body: RunBody) -> dict:
    lesson = get_lesson(request, lesson_id)
    ensure_idle(request, lesson)
    services(request).runner.start_from(lesson, body.from_step)
    return serialize(services(request).store.get(lesson_id) or lesson)


@router.post("/lessons/{lesson_id}/qc/{layer}", status_code=202)
async def rerun_qc(request: Request, lesson_id: str, layer: str) -> dict:
    lesson = get_lesson(request, lesson_id)
    ensure_idle(request, lesson)
    if lesson.current is None:
        raise HTTPException(400, "There is no lesson to check yet.")
    names = {"facts": [StepName.qc_facts], "instruction": [StepName.qc_instruction],
             "both": [StepName.qc_facts, StepName.qc_instruction]}.get(layer)
    if names is None:
        raise HTTPException(404, "Unknown check. Use facts, instruction or both.")
    services(request).runner.start(lesson, names)
    return serialize(services(request).store.get(lesson_id) or lesson)


@router.get("/lessons/{lesson_id}/events")
async def events(request: Request, lesson_id: str) -> StreamingResponse:
    get_lesson(request, lesson_id)
    broker = services(request).broker
    queue = broker.subscribe(lesson_id)

    async def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'], default=str)}\n\n"
        finally:
            broker.unsubscribe(lesson_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/lessons/{lesson_id}/sources/{source_id}")
def read_source(request: Request, lesson_id: str, source_id: str) -> dict:
    lesson = get_lesson(request, lesson_id)
    source = lesson.source(source_id)
    if source is None:
        raise HTTPException(404, "Source not found.")
    data = source.model_dump(mode="json", exclude={"text"})
    data["passages"] = [{"id": f"{source.id}.p{i}", "text": t} for i, t in enumerate(chunk(source.text or source.snippet), 1)][:60]
    return data


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------


class SectionEdit(BaseModel):
    base_version: int
    body_md: str = Field(min_length=1)

    @field_validator("body_md")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A section cannot be empty")
        return value
    title: str | None = None
    minutes: int | None = Field(default=None, ge=2, le=40)
    instructor_notes: str | None = None


class CheckEdit(BaseModel):
    base_version: int
    question: str = Field(min_length=3)
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0)
    explanation: str = ""


class VersionBody(BaseModel):
    base_version: int


async def _mutate(request: Request, lesson_id: str, base_version: int, change) -> dict:
    svc = services(request)
    async with svc.store.lock_for(lesson_id):
        lesson = get_lesson(request, lesson_id)
        try:
            fixes.require_version(lesson, base_version)
            change(lesson)
        except fixes.Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, f"{exc.args[0]} was not found in this lesson.") from exc
        except (ValueError, StepError) as exc:
            raise HTTPException(400, str(exc)) from exc
        svc.store.save(lesson)
    svc.broker.publish(lesson_id, "lesson", {"version": lesson.version_number, "running": lesson.running})
    return serialize(lesson)


@router.put("/lessons/{lesson_id}/sections/{section_id}")
async def edit_section(request: Request, lesson_id: str, section_id: str, body: SectionEdit) -> dict:
    minutes = services(request).settings.lesson_minutes
    return await _mutate(request, lesson_id, body.base_version, lambda l: fixes.edit_section(
        l, section_id, body_md=body.body_md, title=body.title, minutes=body.minutes,
        instructor_notes=body.instructor_notes, total_minutes=minutes))


@router.put("/lessons/{lesson_id}/checks/{check_id}")
async def edit_check(request: Request, lesson_id: str, check_id: str, body: CheckEdit) -> dict:
    return await _mutate(request, lesson_id, body.base_version, lambda l: fixes.edit_check(
        l, check_id, question=body.question, options=body.options, answer_index=body.answer_index,
        explanation=body.explanation))


@router.get("/lessons/{lesson_id}/versions/{number}")
def read_version(request: Request, lesson_id: str, number: int) -> dict:
    lesson = get_lesson(request, lesson_id)
    version = next((v for v in lesson.versions if v.number == number), None)
    if version is None:
        raise HTTPException(404, "Version not found.")
    return version.model_dump(mode="json")


@router.post("/lessons/{lesson_id}/versions/{number}/restore")
async def restore_version(request: Request, lesson_id: str, number: int, body: VersionBody) -> dict:
    return await _mutate(request, lesson_id, body.base_version, lambda l: fixes.restore(l, number))


# ---------------------------------------------------------------------------
# QC findings
# ---------------------------------------------------------------------------


def _issue(lesson: Lesson, issue_id: str):
    issue = lesson.issue(issue_id)
    if issue is None:
        raise HTTPException(404, "Finding not found.")
    return issue


@router.post("/lessons/{lesson_id}/issues/{issue_id}/preview")
async def preview_fix(request: Request, lesson_id: str, issue_id: str) -> dict:
    lesson = get_lesson(request, lesson_id)
    issue = _issue(lesson, issue_id)
    try:
        result = await fixes.preview(step_context(request, lesson), issue)
    except (StepError, LLMError) as exc:
        raise HTTPException(400, str(exc)) from exc
    result["base_version"] = lesson.version_number
    return result


class ApplyBody(BaseModel):
    base_version: int
    after: str | None = None
    check: dict | None = None


@router.post("/lessons/{lesson_id}/issues/{issue_id}/apply")
async def apply_fix(request: Request, lesson_id: str, issue_id: str, body: ApplyBody) -> dict:
    def change(lesson: Lesson):
        fixes.apply(lesson, _issue(lesson, issue_id), after=body.after, check=body.check)
    return await _mutate(request, lesson_id, body.base_version, change)


class DismissBody(BaseModel):
    reason: str | None = None


@router.post("/lessons/{lesson_id}/issues/{issue_id}/dismiss")
async def dismiss_fix(request: Request, lesson_id: str, issue_id: str, body: DismissBody) -> dict:
    svc = services(request)
    async with svc.store.lock_for(lesson_id):
        lesson = get_lesson(request, lesson_id)
        fixes.dismiss(_issue(lesson, issue_id), body.reason)
        svc.store.save(lesson)
    return serialize(lesson)


@router.post("/lessons/{lesson_id}/issues/{issue_id}/reopen")
async def reopen_fix(request: Request, lesson_id: str, issue_id: str) -> dict:
    svc = services(request)
    async with svc.store.lock_for(lesson_id):
        lesson = get_lesson(request, lesson_id)
        issue = _issue(lesson, issue_id)
        issue.status, issue.dismiss_reason = "open", None
        svc.store.save(lesson)
    return serialize(lesson)


@router.post("/lessons/{lesson_id}/apply-exact")
async def apply_exact(request: Request, lesson_id: str, body: VersionBody) -> dict:
    applied: list[str] = []

    def change(lesson: Lesson):
        _, ids = fixes.apply_all_exact(lesson)
        if not ids:
            raise ValueError("There are no open exact fixes to apply.")
        applied.extend(ids)

    data = await _mutate(request, lesson_id, body.base_version, change)
    data["applied"] = applied
    return data


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

EXPORTS = {
    "md": ("text/markdown; charset=utf-8", "md"),
    "html": ("text/html; charset=utf-8", "html"),
    "json": ("application/json", "json"),
    "zip": ("application/zip", "zip"),
}


@router.get("/lessons/{lesson_id}/export")
def export(request: Request, lesson_id: str, format: str = Query("zip")) -> Response:
    lesson = get_lesson(request, lesson_id)
    if lesson.current is None:
        raise HTTPException(400, "There is nothing to export yet.")
    if format not in EXPORTS:
        raise HTTPException(400, "Choose md, html, json or zip.")
    media, ext = EXPORTS[format]
    body = {
        "md": lambda: exporters.lesson_markdown(lesson).encode(),
        "html": lambda: exporters.lesson_html(lesson).encode(),
        "json": lambda: exporters.lesson_json(lesson).encode(),
        "zip": lambda: exporters.bundle(lesson),
    }[format]()
    name = f"{exporters.slug(lesson.request.title)}-v{lesson.version_number}.{ext}"
    return Response(content=body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})
