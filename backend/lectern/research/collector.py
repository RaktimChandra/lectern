"""Turns a research plan into a ranked, de-duplicated list of sources.

Failures are isolated: a query that errors becomes a warning in the research
log and the rest of the research continues. The step only fails when there is
nothing readable to build a lesson from.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlparse, urlunparse

from ..config import Settings
from ..models import LessonRequest, ObjectiveAnalysisOut, ResearchLogEntry, ResearchPlanOut, Source, VideoSegment
from . import reliability
from .passages import relevance
from .providers import (
    BookHit,
    BraveSearch,
    GoogleBooks,
    OpenLibrary,
    ResearchError,
    TavilySearch,
    VideoHit,
    WebHit,
    Wikipedia,
    YouTube,
    best_segment,
    fetch_page,
)

Logger = Callable[[str, str], Awaitable[None] | None]

MIN_RELEVANCE = 0.2
SKIP_EXTENSIONS = (".pdf", ".ppt", ".pptx", ".doc", ".docx", ".zip", ".mp4")
SKIP_HOSTS = ("youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com", "linkedin.com")


@dataclass
class ResearchToolkit:
    web: object | None
    wikipedia: object | None
    youtube: object | None
    books: list
    fetch: Callable[[str, float], Awaitable[tuple[str, str]]] = fetch_page

    @classmethod
    def from_settings(cls, settings: Settings) -> "ResearchToolkit":
        timeout = settings.research_timeout_seconds
        web = None
        if settings.tavily_api_key:
            web = TavilySearch(settings.tavily_api_key, timeout)
        elif settings.brave_api_key:
            web = BraveSearch(settings.brave_api_key, timeout)
        return cls(
            web=web,
            wikipedia=Wikipedia(timeout),
            youtube=YouTube(settings.youtube_api_key, timeout) if settings.youtube_api_key else None,
            books=[GoogleBooks(settings.google_books_api_key, timeout), OpenLibrary(timeout)],
        )


def normalize_url(url: str) -> str:
    parts = urlparse(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunparse((parts.scheme.lower(), host, path, "", parts.query, ""))


class Collector:
    def __init__(self, toolkit: ResearchToolkit, settings: Settings, logger: Logger):
        self.toolkit = toolkit
        self.settings = settings
        self._logger = logger
        self.log: list[ResearchLogEntry] = []

    async def _say(self, message: str, level: str = "info") -> None:
        result = self._logger(message, level)
        if asyncio.iscoroutine(result):
            await result

    def _record(self, provider: str, query: str, results: int = 0, error: str | None = None) -> None:
        self.log.append(ResearchLogEntry(provider=provider, query=query, ok=error is None, results=results, error=error))

    async def run(self, request: LessonRequest, analysis: ObjectiveAnalysisOut, plan: ResearchPlanOut) -> list[Source]:
        terms = _key_terms(request, analysis)
        authoritative = [d.lower().removeprefix("www.") for d in plan.authoritative_domains]

        web_task = self._web(plan, request, terms, authoritative)
        seed_task = self._seeds(request.seed_urls, authoritative)
        wiki_task = self._wikipedia(plan, request, terms)
        video_task = self._videos(plan, terms)
        book_task = self._books(plan, terms)
        web, seeds, wiki, videos, books = await asyncio.gather(web_task, seed_task, wiki_task, video_task, book_task)

        text_sources = seeds + web + wiki
        if not any(s["text"] for s in text_sources):
            raise ResearchError(
                "No readable sources were found. Add a web search key (Tavily or Brave), "
                "paste a few trusted URLs as instructor sources, or rephrase the title."
            )

        ordered = (
            seeds
            + sorted(web, key=lambda s: s["reliability"].score, reverse=True)
            + wiki
            + books
            + videos
        )
        sources = [Source(id=f"S{i}", **entry) for i, entry in enumerate(ordered, start=1)]
        counts = {k: sum(1 for s in sources if s.kind == k) for k in ("instructor", "web", "encyclopedia", "book", "video")}
        await self._say(
            "Collected {total} sources: {web} web pages, {encyclopedia} encyclopedia, {book} books, {video} videos{seed}.".format(
                total=len(sources), seed=f", {counts['instructor']} from you" if counts["instructor"] else "", **counts
            )
        )
        return sources

    # -- web ------------------------------------------------------------------

    async def _web(self, plan, request, terms, authoritative) -> list[dict]:
        if not self.toolkit.web:
            await self._say("No web search key set, so research uses Wikipedia, books, video and your URLs only.", "warn")
            return []
        provider = self.toolkit.web
        semaphore = asyncio.Semaphore(4)

        async def one(query: str) -> list[WebHit]:
            async with semaphore:
                try:
                    hits = await provider.search(query, self.settings.max_web_results_per_query)
                    self._record(provider.name, query, len(hits))
                    return hits
                except Exception as exc:  # isolate each query
                    self._record(provider.name, query, error=str(exc))
                    await self._say(f"Web search failed for '{query}': {exc}", "warn")
                    return []

        queries = [q.query for q in plan.web_queries]
        results = await asyncio.gather(*(one(q) for q in queries))

        seen: dict[str, WebHit] = {}
        for hits in results:
            for hit in hits:
                key = normalize_url(hit.url)
                lowered = key.lower()
                if lowered.endswith(SKIP_EXTENSIONS) or any(h in urlparse(key).netloc for h in SKIP_HOSTS):
                    continue
                if key not in seen or (hit.content and not seen[key].content):
                    seen[key] = hit

        def rank(hit: WebHit) -> float:
            rel = reliability.assess(hit.url, "web", authoritative_domains=authoritative)
            return rel.score * 0.6 + relevance(f"{hit.title} {hit.snippet}", terms) * 0.4

        candidates = sorted(seen.values(), key=rank, reverse=True)[: self.settings.max_pages_to_read]
        await self._say(f"Reading {len(candidates)} of {len(seen)} web results.")
        page_semaphore = asyncio.Semaphore(6)

        async def read(hit: WebHit) -> dict | None:
            text, title = hit.content, hit.title
            if len(text) < 400:
                async with page_semaphore:
                    try:
                        title_found, text = await self.toolkit.fetch(hit.url, self.settings.research_timeout_seconds)
                        title = hit.title or title_found
                        self._record("page", hit.url, 1)
                    except Exception as exc:
                        self._record("page", hit.url, error=str(exc))
                        text = ""
            body = text or hit.snippet
            score = relevance(f"{title} {body[:6000]}", terms)
            if score < MIN_RELEVANCE:
                await self._say(f"Skipped off-topic page: {title}", "info")
                return None
            return {
                "kind": "web",
                "title": title.strip()[:300],
                "url": hit.url,
                "domain": reliability.domain_of(hit.url),
                "snippet": hit.snippet[:600],
                "text": text,
                "reliability": reliability.assess(hit.url, "web", authoritative_domains=authoritative),
                "found_by": hit.query,
            }

        pages = await asyncio.gather(*(read(h) for h in candidates))
        return [p for p in pages if p]

    async def _seeds(self, urls: list[str], authoritative) -> list[dict]:
        async def one(url: str) -> dict | None:
            try:
                title, text = await self.toolkit.fetch(url, self.settings.research_timeout_seconds)
                self._record("instructor", url, 1)
            except Exception as exc:
                self._record("instructor", url, error=str(exc))
                await self._say(f"Could not read your source {url}: {exc}", "warn")
                return None
            return {
                "kind": "instructor",
                "title": title[:300],
                "url": url,
                "domain": reliability.domain_of(url),
                "snippet": text[:400],
                "text": text,
                "reliability": reliability.assess(url, "instructor", authoritative_domains=authoritative),
                "found_by": "Instructor-provided",
            }

        return [s for s in await asyncio.gather(*(one(u) for u in urls)) if s]

    # -- encyclopedia -----------------------------------------------------------

    async def _wikipedia(self, plan, request, terms) -> list[dict]:
        wiki = self.toolkit.wikipedia
        if not wiki:
            return []
        titles = list(dict.fromkeys(plan.wikipedia_titles))[:3]
        try:
            if not titles:
                titles = await wiki.search_titles(request.title, 2)
            self._record("wikipedia", ", ".join(titles) or request.title, len(titles))
        except Exception as exc:
            self._record("wikipedia", request.title, error=str(exc))
            await self._say(f"Wikipedia search failed: {exc}", "warn")
            return []

        async def one(title: str) -> dict | None:
            try:
                article = await wiki.article(title)
            except Exception as exc:
                self._record("wikipedia", title, error=str(exc))
                return None
            if not article:
                self._record("wikipedia", title, error="no such article")
                return None
            real_title, url, text = article
            if relevance(text[:8000], terms) < MIN_RELEVANCE:
                return None
            return {
                "kind": "encyclopedia",
                "title": f"{real_title} (Wikipedia)",
                "url": url or f"https://en.wikipedia.org/wiki/{real_title.replace(' ', '_')}",
                "domain": "wikipedia.org",
                "publisher": "Wikipedia",
                "snippet": text[:400],
                "text": text,
                "reliability": reliability.assess("https://en.wikipedia.org", "encyclopedia"),
                "found_by": title,
            }

        return [a for a in await asyncio.gather(*(one(t) for t in titles)) if a]

    # -- video -------------------------------------------------------------------

    async def _videos(self, plan, terms) -> list[dict]:
        yt = self.toolkit.youtube
        if not yt:
            await self._say("No YouTube key set, so the lesson will not recommend videos.", "warn")
            return []
        found: dict[str, VideoHit] = {}
        for query in plan.video_queries:
            try:
                hits = await yt.search(query, 5)
                self._record("youtube", query, len(hits))
            except Exception as exc:
                self._record("youtube", query, error=str(exc))
                await self._say(f"YouTube search failed for '{query}': {exc}", "warn")
                continue
            for hit in hits:
                found.setdefault(hit.video_id, hit)

        candidates = [h for h in found.values() if not h.duration_seconds or 120 <= h.duration_seconds <= 3600]
        candidates.sort(key=lambda h: relevance(f"{h.title} {h.description}", terms), reverse=True)
        candidates = candidates[: self.settings.max_videos + 4]
        await asyncio.gather(*(yt.attach_transcript(h) for h in candidates))

        def score(hit: VideoHit) -> float:
            text = " ".join(t for _, _, t in hit.transcript) if hit.transcript else f"{hit.title} {hit.description}"
            fit = 1.0 if hit.duration_seconds and 240 <= hit.duration_seconds <= 1500 else 0.7
            views = min((hit.view_count or 0) / 1_000_000, 1.0)
            return relevance(text[:20000], terms) * 0.6 + fit * 0.25 + views * 0.15

        chosen = sorted(candidates, key=score, reverse=True)[: self.settings.max_videos]
        entries = []
        for hit in chosen:
            transcript_text = " ".join(t for _, _, t in hit.transcript)
            segment = best_segment(hit.transcript, terms)
            entries.append(
                {
                    "kind": "video",
                    "title": hit.title,
                    "url": hit.url,
                    "domain": "youtube.com",
                    "publisher": hit.channel,
                    "channel": hit.channel,
                    "year": hit.published_year,
                    "snippet": hit.description[:400],
                    "text": transcript_text[:40000],
                    "duration_seconds": hit.duration_seconds,
                    "view_count": hit.view_count,
                    "has_transcript": bool(hit.transcript),
                    "best_segment": VideoSegment(start_seconds=segment[0], end_seconds=segment[1], excerpt=segment[2]) if segment else None,
                    "reliability": reliability.assess(hit.url, "video", view_count=hit.view_count, has_transcript=bool(hit.transcript)),
                    "found_by": hit.query,
                }
            )
        return entries

    # -- books --------------------------------------------------------------------

    async def _books(self, plan, terms) -> list[dict]:
        found: dict[str, BookHit] = {}
        for query in plan.book_queries:
            for provider in self.toolkit.books:
                try:
                    hits = await provider.search(query, 5)
                    self._record(provider.name, query, len(hits))
                except Exception as exc:
                    self._record(provider.name, query, error=str(exc))
                    continue
                for hit in hits:
                    key = "".join(ch for ch in hit.title.lower() if ch.isalnum())[:60]
                    existing = found.get(key)
                    if not existing or (hit.description and not existing.description):
                        found[key] = hit
        if not found:
            await self._say("No book references were found.", "warn")

        def score(hit: BookHit) -> float:
            rel = reliability.assess(hit.url, "book", publisher=hit.publisher)
            recency = 1.0 if hit.year and hit.year >= 2012 else 0.6
            return relevance(f"{hit.title} {hit.description}", terms) * 0.6 + rel.score * 0.25 + recency * 0.15

        chosen = [h for h in sorted(found.values(), key=score, reverse=True) if h.url][: self.settings.max_books]
        return [
            {
                "kind": "book",
                "title": hit.title,
                "url": hit.url,
                "domain": reliability.domain_of(hit.url),
                "publisher": hit.publisher,
                "authors": hit.authors,
                "year": hit.year,
                "isbn": hit.isbn,
                "snippet": hit.description[:400],
                "text": hit.description,
                "reliability": reliability.assess(hit.url, "book", publisher=hit.publisher),
                "found_by": hit.query,
            }
            for hit in chosen
        ]


def _key_terms(request: LessonRequest, analysis: ObjectiveAnalysisOut) -> list[str]:
    terms = [t for atom in analysis.atoms for t in atom.key_terms]
    terms += [w for w in request.title.split() if len(w) > 3]
    return list(dict.fromkeys(terms))
