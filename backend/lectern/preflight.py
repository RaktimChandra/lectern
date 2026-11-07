"""Connection check: one small, real request to every configured service.

Run before generating a lesson (the "Check connections" button) so a wrong key,
a retired model or a disabled API shows up in seconds, with the service named,
instead of minutes into a lesson.
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from pydantic import BaseModel

from .llm.base import LLMClient


class _Ping(BaseModel):
    ok: bool
    word: str


async def _timed(name: str, role: str, work: Callable[[], Awaitable[str]], timeout: float) -> dict:
    started = time.perf_counter()
    try:
        detail = await asyncio.wait_for(work(), timeout=timeout)
        ok = True
    except asyncio.TimeoutError:
        ok, detail = False, f"no answer within {int(timeout)} s"
    except Exception as exc:  # noqa: BLE001 - every failure becomes a readable row
        ok, detail = False, str(exc) or type(exc).__name__
    return {"name": name, "role": role, "ok": ok, "detail": detail[:300],
            "ms": int((time.perf_counter() - started) * 1000)}


def _llm_check(client: LLMClient) -> Callable[[], Awaitable[str]]:
    async def work() -> str:
        result = await client.structured(
            "connection check",
            system="You are a connectivity probe. Answer briefly.",
            user='Return {"ok": true, "word": "ready"}.',
            schema=_Ping, temperature=0.0, max_tokens=2000,
        )
        if not result.ok:
            raise RuntimeError("the model answered, but not as instructed")
        return f"{client.provider} · {client.model}"
    return work


async def run_preflight(writer: LLMClient | None, reviewer: LLMClient | None, toolkit) -> list[dict]:
    jobs: list[Awaitable[dict]] = []
    rows: list[dict] = []

    if writer is None:
        rows.append({"name": "Writer model", "role": "required", "ok": False, "ms": 0,
                     "detail": "No model key in .env (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY or OPENROUTER_API_KEY)."})
    else:
        jobs.append(_timed("Writer model", "required", _llm_check(writer), 90))
    if reviewer is not None and (writer is None or reviewer.label != writer.label):
        jobs.append(_timed("Reviewer model", "required", _llm_check(reviewer), 90))

    if toolkit.web is None:
        rows.append({"name": "Web search", "role": "recommended", "ok": False, "ms": 0,
                     "detail": "No TAVILY_API_KEY or BRAVE_API_KEY; research will use Wikipedia, books and your own links only."})
    else:
        async def web() -> str:
            hits = await toolkit.web.search("HTTP request methods", 1)
            return f"{getattr(toolkit.web, 'name', 'web')} · {len(hits)} result(s)"
        jobs.append(_timed("Web search", "recommended", web, 30))

    if toolkit.youtube is None:
        rows.append({"name": "YouTube", "role": "recommended", "ok": False, "ms": 0,
                     "detail": "No YOUTUBE_API_KEY; the lesson will have no video recommendations."})
    else:
        async def youtube() -> str:
            hits = await toolkit.youtube.search("HTTP status codes explained", 1)
            return f"{len(hits)} video(s) found"
        jobs.append(_timed("YouTube", "recommended", youtube, 30))

    if toolkit.wikipedia is not None:
        async def wiki() -> str:
            titles = await toolkit.wikipedia.search_titles("Hypertext Transfer Protocol", 1)
            if not titles:
                raise RuntimeError("search returned nothing")
            return f"found “{titles[0]}”"
        jobs.append(_timed("Wikipedia", "keyless", wiki, 20))

    for books in toolkit.books:
        async def book(provider=books) -> str:
            hits = await provider.search("HTTP definitive guide", 1)
            return f"{len(hits)} record(s)"
        label = "Google Books" if getattr(books, "name", "") == "google_books" else "Open Library"
        jobs.append(_timed(label, "keyless", book, 20))

    rows.extend(await asyncio.gather(*jobs))
    order = ["Writer model", "Reviewer model", "Web search", "YouTube", "Wikipedia", "Google Books", "Open Library"]
    rows.sort(key=lambda r: order.index(r["name"]) if r["name"] in order else 99)
    return rows
