"""FastAPI application. In production it also serves the built frontend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import ROOT_DIR, Settings, get_settings
from .events import EventBroker
from .llm.base import LLMClient
from .llm.providers import build_client
from .pipeline.runner import Runner, recover_interrupted
from .research.collector import ResearchToolkit
from . import security
from .store import LessonStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs every request URL at INFO, and some APIs (YouTube, Google Books) take
# the key as a query parameter; keep keys out of the console and any log files.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

FIELD_NAMES = {"title": "Lesson title", "objective": "Learning objective", "seed_urls": "Your sources",
               "audience": "Audience", "mode": "Delivery"}


@dataclass
class Services:
    settings: Settings
    store: LessonStore
    broker: EventBroker
    runner: Runner
    models: Callable[[], tuple[LLMClient | None, LLMClient | None]]
    toolkit: Callable[[], ResearchToolkit]


def default_models(settings: Settings):
    def make() -> tuple[LLMClient | None, LLMClient | None]:
        writer = settings.resolve_writer()
        reviewer = settings.resolve_reviewer()
        return (build_client(*writer, settings) if writer else None,
                build_client(*reviewer, settings) if reviewer else None)
    return make


def create_app(settings: Settings | None = None, *, models=None, toolkit=None, store: LessonStore | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = store or LessonStore(settings.db_path)
    broker = EventBroker()
    models = models or default_models(settings)
    toolkit = toolkit or (lambda: ResearchToolkit.from_settings(settings))
    runner = Runner(store, broker, settings, models, toolkit)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recovered = recover_interrupted(store)
        if recovered:
            logging.getLogger("lectern").info("Marked %d interrupted lesson(s) as failed so they can be retried.", recovered)
        yield

    app = FastAPI(title="Lectern", version="1.1.0", lifespan=lifespan)
    app.state.services = Services(settings, store, broker, runner, models, toolkit)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"],
                       allow_credentials=True)
    security.install(app, settings)
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def readable_validation(_: Request, exc: RequestValidationError):
        messages = []
        for err in exc.errors():
            field = next((str(p) for p in reversed(err["loc"]) if isinstance(p, str) and p != "body"), "")
            label = FIELD_NAMES.get(field, field.replace("_", " ").capitalize())
            msg = err["msg"].removeprefix("Value error, ")
            if err["type"] in ("string_too_short", "missing"):
                msg = "cannot be empty"
            messages.append({"field": field, "message": f"{label}: {msg}" if label else msg})
        return JSONResponse(status_code=422, content={"detail": "; ".join(m["message"] for m in messages), "errors": messages})

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path == "api" or path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not found."})
            file = FRONTEND_DIST / path
            if path and file.is_file() and FRONTEND_DIST in file.resolve().parents:
                return FileResponse(file)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


def _lazy_app() -> FastAPI:
    return create_app()


app = _lazy_app()
