"""Research providers: web search, page reading, Wikipedia, YouTube and books.

Every provider returns plain dataclasses and raises `ResearchError` with a
readable message on failure. The collector decides what a failure means (one
failed query is a warning; no readable sources at all stops the step).
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx
import trafilatura

USER_AGENT = "Lectern/1.1 (+https://github.com/RaktimChandra/lectern; educational lesson research)"
MAX_TEXT_CHARS = 60_000


class ResearchError(RuntimeError):
    pass


@dataclass
class WebHit:
    title: str
    url: str
    snippet: str
    content: str = ""  # full text when the provider supplies it
    query: str = ""


@dataclass
class VideoHit:
    video_id: str
    title: str
    channel: str
    description: str
    published_year: int | None
    duration_seconds: int | None = None
    view_count: int | None = None
    transcript: list[tuple[float, float, str]] = field(default_factory=list)  # (start, duration, text)
    query: str = ""

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class BookHit:
    title: str
    authors: list[str]
    publisher: str
    year: int | None
    description: str
    url: str
    isbn: str | None
    query: str = ""


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _check(response: httpx.Response, service: str) -> None:
    if response.status_code in (401, 403):
        raise ResearchError(f"{service} rejected the API key ({response.status_code}).")
    if response.status_code == 429:
        raise ResearchError(f"{service} rate limit reached.")
    if response.status_code >= 400:
        raise ResearchError(f"{service} returned {response.status_code}.")


# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------


class TavilySearch:
    name = "tavily"
    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout: float):
        self.api_key, self.timeout = api_key, timeout

    async def search(self, query: str, limit: int) -> list[WebHit]:
        body = {
            "query": query,
            "max_results": limit,
            "search_depth": "advanced",
            "include_raw_content": True,
            "api_key": self.api_key,
        }
        async with _client(self.timeout) as client:
            response = await client.post(self.endpoint, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        _check(response, "Tavily")
        return parse_tavily(response.json(), query)


_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^)]*\))*\)")


def markdown_to_text(text: str) -> str:
    """Tavily raw_content is Markdown; keep link text, drop URLs and images so quotes can match verbatim."""
    text = _MD_IMAGE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    return text.replace("**", "").replace("__", "")


def parse_tavily(data: dict, query: str) -> list[WebHit]:
    hits = []
    for item in data.get("results", []):
        if not item.get("url"):
            continue
        hits.append(
            WebHit(
                title=item.get("title") or item["url"],
                url=item["url"],
                snippet=(item.get("content") or "")[:600],
                content=markdown_to_text(item.get("raw_content") or "")[:MAX_TEXT_CHARS],
                query=query,
            )
        )
    return hits


class BraveSearch:
    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, timeout: float):
        self.api_key, self.timeout = api_key, timeout

    async def search(self, query: str, limit: int) -> list[WebHit]:
        async with _client(self.timeout) as client:
            response = await client.get(
                self.endpoint,
                params={"q": query, "count": limit},
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            )
        _check(response, "Brave Search")
        return parse_brave(response.json(), query)


def parse_brave(data: dict, query: str) -> list[WebHit]:
    hits = []
    for item in (data.get("web") or {}).get("results", []):
        if item.get("url"):
            snippet = re.sub(r"<[^>]+>", "", item.get("description") or "")
            hits.append(WebHit(title=item.get("title") or item["url"], url=item["url"], snippet=snippet, query=query))
    return hits


# ---------------------------------------------------------------------------
# Page reading
# ---------------------------------------------------------------------------


MAX_PAGE_BYTES = 4_000_000
MAX_REDIRECTS = 5


async def ensure_public_url(url: str) -> None:
    """Refuse URLs that point at this machine or a private network.

    Pages are fetched on the server, so an address such as 127.0.0.1 or a cloud
    metadata endpoint must never be read and shown back to the user.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ResearchError(f"{url} is not a web address")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ResearchError(f"could not find the site {parts.hostname}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
                or address.is_multicast or address.is_unspecified):
            raise ResearchError(f"{url} points to a private or local address, which Lectern does not read")


async def fetch_page(url: str, timeout: float) -> tuple[str, str]:
    """Download a public page and return (title, main text). Raises ResearchError if nothing readable."""
    try:
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await ensure_public_url(url)
                async with client.stream("GET", url) as response:
                    if response.is_redirect and "location" in response.headers:
                        url = str(response.url.join(response.headers["location"]))
                        continue
                    _check(response, url)
                    content_type = response.headers.get("content-type", "")
                    if "html" not in content_type and "text" not in content_type:
                        raise ResearchError(f"{url} is not a web page ({content_type or 'unknown type'})")
                    body = bytearray()
                    async for chunk_bytes in response.aiter_bytes():
                        body.extend(chunk_bytes)
                        if len(body) > MAX_PAGE_BYTES:
                            break
                    html = bytes(body).decode(response.encoding or "utf-8", errors="replace")
                    break
            else:
                raise ResearchError(f"{url} redirected too many times")
    except httpx.HTTPError as exc:
        raise ResearchError(f"could not download {url} ({type(exc).__name__})") from exc
    text = await asyncio.to_thread(
        trafilatura.extract, html, include_comments=False, include_tables=True, favor_precision=True
    )
    if not text or len(text) < 200:
        raise ResearchError(f"no readable article text on {url}")
    metadata = await asyncio.to_thread(trafilatura.extract_metadata, html)
    title = (metadata.title if metadata and metadata.title else "") or url
    return title, text[:MAX_TEXT_CHARS]


# ---------------------------------------------------------------------------
# Wikipedia (no key)
# ---------------------------------------------------------------------------


class Wikipedia:
    name = "wikipedia"
    endpoint = "https://en.wikipedia.org/w/api.php"

    def __init__(self, timeout: float):
        self.timeout = timeout

    async def search_titles(self, query: str, limit: int = 2) -> list[str]:
        params = {"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "format": "json"}
        async with _client(self.timeout) as client:
            response = await client.get(self.endpoint, params=params)
        _check(response, "Wikipedia")
        return [r["title"] for r in response.json().get("query", {}).get("search", [])]

    async def article(self, title: str) -> tuple[str, str, str] | None:
        """Return (title, url, plain text) or None if the page does not exist."""
        params = {
            "action": "query", "prop": "extracts|info", "explaintext": 1, "inprop": "url",
            "titles": title, "redirects": 1, "format": "json",
        }
        async with _client(self.timeout) as client:
            response = await client.get(self.endpoint, params=params)
        _check(response, "Wikipedia")
        return parse_wikipedia_article(response.json())


def parse_wikipedia_article(data: dict) -> tuple[str, str, str] | None:
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        if "missing" in page or not page.get("extract"):
            continue
        text = page["extract"]
        # Drop trailing reference-style sections that add noise to evidence search.
        text = re.split(r"\n==\s*(See also|References|External links|Further reading|Notes)\s*==", text)[0]
        text = re.sub(r"\n=+\s*([^=]+?)\s*=+\n", r"\n\n\1\n\n", text)
        return page.get("title", ""), page.get("fullurl", ""), text[:MAX_TEXT_CHARS]
    return None


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

_ISO_DURATION = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_iso_duration(value: str) -> int | None:
    match = _ISO_DURATION.fullmatch(value or "")
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class YouTube:
    name = "youtube"
    base = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, timeout: float):
        self.api_key, self.timeout = api_key, timeout

    async def search(self, query: str, limit: int) -> list[VideoHit]:
        params = {
            "part": "snippet", "type": "video", "q": query, "maxResults": limit, "relevanceLanguage": "en",
            "safeSearch": "strict", "videoEmbeddable": "true", "key": self.api_key,
        }
        async with _client(self.timeout) as client:
            response = await client.get(f"{self.base}/search", params=params)
            _check(response, "YouTube Data API")
            hits = parse_youtube_search(response.json(), query)
            if not hits:
                return []
            details = await client.get(
                f"{self.base}/videos",
                params={"part": "contentDetails,statistics", "id": ",".join(h.video_id for h in hits), "key": self.api_key},
            )
            _check(details, "YouTube Data API")
        apply_youtube_details(hits, details.json())
        return hits

    async def attach_transcript(self, hit: VideoHit) -> None:
        """Best effort: many videos have no transcript, and YouTube may block automated access."""
        hit.transcript = await asyncio.to_thread(_fetch_transcript, hit.video_id)


def _fetch_transcript(video_id: str) -> list[tuple[float, float, str]]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch(video_id, languages=("en", "en-US", "en-GB"))
        return [(s.start, s.duration, s.text) for s in fetched]
    except Exception:  # transcripts are optional: disabled, missing or blocked
        return []


def parse_youtube_search(data: dict, query: str) -> list[VideoHit]:
    hits = []
    for item in data.get("items", []):
        video_id = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        if not video_id:
            continue
        published = snippet.get("publishedAt") or ""
        hits.append(
            VideoHit(
                video_id=video_id,
                title=_unescape(snippet.get("title", "")),
                channel=snippet.get("channelTitle", ""),
                description=_unescape(snippet.get("description", "")),
                published_year=int(published[:4]) if published[:4].isdigit() else None,
                query=query,
            )
        )
    return hits


def apply_youtube_details(hits: list[VideoHit], data: dict) -> None:
    by_id = {item.get("id"): item for item in data.get("items", [])}
    for hit in hits:
        item = by_id.get(hit.video_id) or {}
        hit.duration_seconds = parse_iso_duration((item.get("contentDetails") or {}).get("duration", ""))
        views = (item.get("statistics") or {}).get("viewCount")
        hit.view_count = int(views) if views and str(views).isdigit() else None


def _unescape(text: str) -> str:
    return text.replace("&#39;", "'").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def best_segment(transcript: list[tuple[float, float, str]], terms: list[str], window_seconds: int = 300):
    """Find the stretch of the video that talks most about the lesson's key terms.

    Returns (start, end, excerpt) or None. Lets the lesson say "watch 2:10–6:40"
    instead of sending learners into a 40-minute video.
    """
    from .passages import tokenize

    if not transcript:
        return None
    wanted = {t for term in terms for t in tokenize(term)}
    if not wanted:
        return None
    best = None
    for i, (start, _, _) in enumerate(transcript):
        score, end, texts = 0, start, []
        for s, d, text in transcript[i:]:
            if s - start > window_seconds:
                break
            score += sum(1 for tok in tokenize(text) if tok in wanted)
            end = s + d
            texts.append(text)
        if score and (best is None or score > best[0]):
            best = (score, int(start), int(end), " ".join(texts))
    if not best or best[0] < 3:
        return None
    _, start, end, excerpt = best
    return start, end, " ".join(excerpt.split())[:600]


# ---------------------------------------------------------------------------
# Books (keyless: Google Books at low quota, Open Library)
# ---------------------------------------------------------------------------


class GoogleBooks:
    name = "google_books"
    endpoint = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, api_key: str | None, timeout: float):
        self.api_key, self.timeout = api_key, timeout

    async def search(self, query: str, limit: int) -> list[BookHit]:
        params = {"q": query, "maxResults": limit, "printType": "books", "langRestrict": "en", "orderBy": "relevance"}
        if self.api_key:
            params["key"] = self.api_key
        async with _client(self.timeout) as client:
            response = await client.get(self.endpoint, params=params)
        _check(response, "Google Books")
        return parse_google_books(response.json(), query)


def parse_google_books(data: dict, query: str) -> list[BookHit]:
    hits = []
    for item in data.get("items", []):
        info = item.get("volumeInfo") or {}
        if not info.get("title"):
            continue
        isbn = next(
            (i["identifier"] for i in info.get("industryIdentifiers", []) if i.get("type") == "ISBN_13"),
            next((i["identifier"] for i in info.get("industryIdentifiers", []) if i.get("type") == "ISBN_10"), None),
        )
        date = info.get("publishedDate") or ""
        title = info["title"] + (f": {info['subtitle']}" if info.get("subtitle") else "")
        hits.append(
            BookHit(
                title=title,
                authors=info.get("authors", []),
                publisher=info.get("publisher", ""),
                year=int(date[:4]) if date[:4].isdigit() else None,
                description=re.sub(r"<[^>]+>", "", info.get("description", "")),
                url=info.get("infoLink") or info.get("canonicalVolumeLink") or "",
                isbn=isbn,
                query=query,
            )
        )
    return hits


class OpenLibrary:
    name = "open_library"
    endpoint = "https://openlibrary.org/search.json"

    def __init__(self, timeout: float):
        self.timeout = timeout

    async def search(self, query: str, limit: int) -> list[BookHit]:
        params = {"q": query, "limit": limit, "fields": "title,subtitle,author_name,first_publish_year,isbn,key,publisher"}
        async with _client(self.timeout) as client:
            response = await client.get(self.endpoint, params=params)
        _check(response, "Open Library")
        return parse_open_library(response.json(), query)


def parse_open_library(data: dict, query: str) -> list[BookHit]:
    hits = []
    for doc in data.get("docs", []):
        if not doc.get("title") or not doc.get("key"):
            continue
        title = doc["title"] + (f": {doc['subtitle']}" if doc.get("subtitle") else "")
        isbns = doc.get("isbn") or []
        hits.append(
            BookHit(
                title=title,
                authors=doc.get("author_name", [])[:4],
                publisher=(doc.get("publisher") or [""])[0],
                year=doc.get("first_publish_year"),
                description="",
                url=f"https://openlibrary.org{doc['key']}",
                isbn=next((i for i in isbns if len(i) == 13), isbns[0] if isbns else None),
                query=query,
            )
        )
    return hits
