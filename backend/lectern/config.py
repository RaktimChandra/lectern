"""Runtime configuration, read from environment variables or a `.env` file.

Nothing secret is ever returned by the API: `Settings.public_status()` reports
only which providers are configured, never the keys themselves.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["anthropic", "openai", "gemini", "openrouter", "ollama"]

# Base URLs for providers that speak the OpenAI chat-completions protocol.
OPENAI_COMPATIBLE_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}

DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4.1",
    "gemini": "gemini-2.5-flash",
    "openrouter": "anthropic/claude-sonnet-5-5",
    "ollama": "llama3.1",
}

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Language models -------------------------------------------------
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None

    # Writer model: drafts the lesson. Leave empty to auto-pick from keys.
    llm_provider: ProviderName | None = None
    llm_model: str | None = None

    # Reviewer model: runs both QC layers. Using a different provider or model
    # from the writer makes the review genuinely independent.
    qc_provider: ProviderName | None = None
    qc_model: str | None = None

    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3

    # --- Research --------------------------------------------------------
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    youtube_api_key: str | None = None
    google_books_api_key: str | None = None  # optional; works keyless at low quota

    research_timeout_seconds: float = 20.0
    max_web_results_per_query: int = 5
    max_pages_to_read: int = 14
    max_videos: int = 6
    max_books: int = 6

    # --- Lesson ----------------------------------------------------------
    lesson_minutes: int = 45
    reading_words_per_minute: int = Field(default=180, ge=60, le=400)

    # --- Storage / server --------------------------------------------------
    data_dir: Path = ROOT_DIR / "data"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "lectern.sqlite3"

    def key_for(self, provider: str) -> str | None:
        return {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "openrouter": self.openrouter_api_key,
            "ollama": "ollama",  # local server, no key
        }.get(provider)

    def resolve_writer(self) -> tuple[str, str] | None:
        provider = self.llm_provider or self._first_configured_provider()
        if provider is None or not self.key_for(provider):
            return None
        return provider, self.llm_model or DEFAULT_MODELS[provider]

    def resolve_reviewer(self) -> tuple[str, str] | None:
        if self.qc_provider:
            if not self.key_for(self.qc_provider):
                return None
            return self.qc_provider, self.qc_model or DEFAULT_MODELS[self.qc_provider]
        writer = self.resolve_writer()
        if writer is None:
            return None
        return writer[0], self.qc_model or writer[1]

    def _first_configured_provider(self) -> str | None:
        for name in ("anthropic", "openai", "gemini", "openrouter"):
            if self.key_for(name):
                return name
        return None

    def public_status(self) -> dict:
        writer = self.resolve_writer()
        reviewer = self.resolve_reviewer()
        web = "tavily" if self.tavily_api_key else ("brave" if self.brave_api_key else None)
        return {
            "writer": {"provider": writer[0], "model": writer[1]} if writer else None,
            "reviewer": {"provider": reviewer[0], "model": reviewer[1]} if reviewer else None,
            "independent_reviewer": bool(writer and reviewer and writer != reviewer),
            "research": {
                "web_search": web,
                "wikipedia": True,
                "youtube": bool(self.youtube_api_key),
                "books": "google_books+open_library",
            },
            "lesson_minutes": self.lesson_minutes,
        }


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
