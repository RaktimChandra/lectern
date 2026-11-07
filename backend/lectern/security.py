"""Protection for running Lectern somewhere other people can reach it.

Locally none of this is noticeable. When Lectern is hosted, three things matter:

1. Access. If ACCESS_TOKEN is set, every API call needs it. The browser sends
   it once to /api/auth and gets an HttpOnly cookie back (EventSource cannot
   send custom headers, so a cookie is what lets live progress keep working).
   Scripts can send it as an `X-Lectern-Key` header instead.
2. Spend. Generating a lesson costs model and search credits, so new lessons
   and other model-backed actions are rate limited per client.
3. Browser hardening: security headers and a strict Content Security Policy;
   the interface loads nothing from other origins.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings

COOKIE = "lectern_key"
OPEN_PATHS = {"/api/health", "/api/auth"}
MAX_BODY_BYTES = 512_000  # lesson requests and edits are small; refuse anything absurd

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'"
    ),
}


def _is_expensive(method: str, path: str) -> bool:
    """Routes that call a model or a paid search API."""
    if method != "POST":
        return False
    return (path in ("/api/preflight",) or path.endswith("/run") or "/qc/" in path or path.endswith("/preview"))


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float) -> tuple[bool, int]:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return False, int(window - (now - hits[0])) + 1
        hits.append(now)
        return True, 0


def client_id(request: Request, settings: Settings) -> str:
    if settings.behind_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def cookie_value(token: str) -> str:
    # The cookie holds a digest, not the passphrase itself.
    return hashlib.sha256(f"lectern-session:{token}".encode()).hexdigest()


def token_ok(request: Request, settings: Settings) -> bool:
    expected = settings.access_token
    if not expected:
        return True
    header = request.headers.get("x-lectern-key")
    if header is not None:
        return hmac.compare_digest(header.encode(), expected.encode())
    cookie = request.cookies.get(COOKIE) or ""
    return hmac.compare_digest(cookie.encode(), cookie_value(expected).encode())


class GuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.limits = SlidingWindow()

    async def dispatch(self, request: Request, call_next):
        path, method = request.url.path, request.method
        if path.startswith("/api"):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request is too large."})
            if path not in OPEN_PATHS and not token_ok(request, self.settings):
                return JSONResponse(status_code=401, content={"detail": "This Lectern is private. Enter the access passphrase."})
            who = client_id(request, self.settings)
            checks = [("all", self.settings.requests_per_minute, 60.0)]
            if method == "POST" and path == "/api/lessons":
                checks.append(("lesson", self.settings.lessons_per_hour, 3600.0))
            elif _is_expensive(method, path):
                checks.append(("model", self.settings.lessons_per_hour * 8, 3600.0))
            if path == "/api/auth":
                checks.append(("auth", 10, 300.0))  # slows down passphrase guessing
            for bucket, limit, window in checks:
                allowed, wait = self.limits.allow(f"{bucket}:{who}", limit, window)
                if not allowed:
                    return JSONResponse(status_code=429, headers={"Retry-After": str(wait)},
                                        content={"detail": f"Too many requests. Try again in {wait} s."})
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class AuthBody(BaseModel):
    token: str


def install(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(GuardMiddleware, settings=settings)

    @app.post("/api/auth", include_in_schema=False)
    async def auth(request: Request, body: AuthBody):
        if not settings.access_token:
            return {"ok": True, "protected": False}
        if not hmac.compare_digest(body.token.strip().encode(), settings.access_token.encode()):
            return JSONResponse(status_code=401, content={"detail": "That passphrase is not right."})
        response = JSONResponse({"ok": True, "protected": True})
        secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(COOKIE, cookie_value(settings.access_token), httponly=True, samesite="strict", secure=secure,
                            max_age=60 * 60 * 24 * 14, path="/")
        return response
