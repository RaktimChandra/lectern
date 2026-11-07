"""Provider-neutral interface for structured LLM calls.

Every call in Lectern asks for JSON that matches a Pydantic model. The client:

1. sends the schema to the provider (as a forced tool call for Anthropic, as a
   JSON response format plus the schema in the prompt for OpenAI-compatible APIs);
2. retries network errors, rate limits and 5xx responses with backoff;
3. validates the reply, and if it does not match the schema, sends the
   validation errors back once and asks for a corrected reply.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .json_utils import extract_json, inline_schema

log = logging.getLogger("lectern.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when a model call fails after all retries. The message is shown to the user."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class LLMClient(ABC):
    provider: str
    model: str

    def __init__(self, *, provider: str, model: str, timeout: float = 120.0, max_retries: int = 3):
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    async def structured(
        self,
        task: str,
        *,
        system: str,
        user: str,
        schema: type[T],
        temperature: float = 0.2,
        max_tokens: int = 8000,
    ) -> T:
        json_schema = inline_schema(schema.model_json_schema())
        raw = await self._with_retries(task, system, user, json_schema, temperature, max_tokens)
        try:
            return schema.model_validate(raw)
        except ValidationError as first_error:
            log.warning("%s: reply did not match schema, asking for a correction", task)
            repair_user = (
                f"{user}\n\n---\nYour previous reply did not match the required schema.\n"
                f"Previous reply:\n{json.dumps(raw)[:6000]}\n\nValidation errors:\n{_short_errors(first_error)}\n"
                "Return a corrected reply that matches the schema exactly."
            )
            raw = await self._with_retries(task, system, repair_user, json_schema, temperature, max_tokens)
            try:
                return schema.model_validate(raw)
            except ValidationError as second_error:
                raise LLMError(
                    f"The {self.provider} model returned data in the wrong shape for '{task}' twice: "
                    f"{_short_errors(second_error)}"
                ) from second_error

    async def _with_retries(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._call(task, system, user, json_schema, temperature, max_tokens)
            except LLMError as exc:
                if not exc.retryable or attempt == self.max_retries:
                    raise
                last_error = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise LLMError(f"Could not reach {self.provider} ({type(exc).__name__}). Check your connection and retry.") from exc
            delay = min(2 ** attempt + random.uniform(0, 1), 20)
            log.info("%s: attempt %d failed (%s); retrying in %.1fs", task, attempt, last_error, delay)
            await asyncio.sleep(delay)
        raise LLMError(str(last_error))  # pragma: no cover

    @abstractmethod
    async def _call(self, task, system, user, json_schema, temperature, max_tokens) -> dict: ...


def raise_for_status(provider: str, response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    detail = response.text[:300]
    if response.status_code in (401, 403):
        raise LLMError(f"{provider} rejected the API key ({response.status_code}). Check the key in your .env file.", retryable=False)
    if response.status_code == 404:
        raise LLMError(f"{provider} does not recognise the model or endpoint (404): {detail}", retryable=False)
    if response.status_code == 400:
        raise LLMError(f"{provider} rejected the request (400): {detail}", retryable=False)
    if response.status_code == 429:
        raise LLMError(f"{provider} rate limit reached (429). Wait a moment and retry.")
    raise LLMError(f"{provider} returned {response.status_code}: {detail}")


def parse_json_text(provider: str, text: str) -> dict:
    try:
        return extract_json(text)
    except ValueError as exc:
        raise LLMError(f"{provider} reply was not valid JSON: {exc}") from exc


def _short_errors(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:8]:
        loc = ".".join(str(p) for p in item["loc"])
        parts.append(f"{loc}: {item['msg']}")
    return "; ".join(parts)
