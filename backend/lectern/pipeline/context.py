"""What every pipeline step receives: the lesson, the models, the research tools and a logger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from ..config import Settings
from ..llm.base import LLMClient
from ..models import Lesson, Source
from ..research.collector import ResearchToolkit
from ..research.passages import Passage, PassageIndex

LogFn = Callable[[str, str], Awaitable[None]]


class StepError(RuntimeError):
    """A step failed in a way the user can act on. The message is shown as is."""


@dataclass
class StepContext:
    lesson: Lesson
    settings: Settings
    writer: LLMClient | None
    reviewer: LLMClient | None
    toolkit: ResearchToolkit
    log: LogFn
    _index: PassageIndex | None = None

    def require_writer(self) -> LLMClient:
        if self.writer is None:
            raise StepError(
                "No AI model is configured. Add ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY to the .env file, "
                "restart Lectern and retry."
            )
        return self.writer

    def require_reviewer(self) -> LLMClient:
        if self.reviewer is None:
            return self.require_writer()
        return self.reviewer

    @property
    def index(self) -> PassageIndex:
        if self._index is None:
            self._index = PassageIndex.from_sources(self.lesson.sources)
        return self._index


def source_label(source: Source) -> str:
    tier = source.reliability.tier.replace("_", " ")
    return f"{source.title}, {tier}"


def evidence_for(ctx: StepContext, query: str, k: int = 5, prefer: list[str] | None = None,
                 max_chars: int = 700) -> list[tuple[str, str, str]]:
    """Top passages for a query as (passage_or_source_id, label, text) tuples."""
    results = ctx.index.search(query, k=k, prefer_sources=prefer)
    out = []
    for passage, _score in results:
        source = ctx.lesson.source(passage.source_id)
        if not source:
            continue
        out.append((passage.source_id, source_label(source), _trim(passage, max_chars)))
    return out


def _trim(passage: Passage, max_chars: int) -> str:
    text = passage.text
    return text if len(text) <= max_chars else text[: max_chars].rsplit(" ", 1)[0] + " ..."
