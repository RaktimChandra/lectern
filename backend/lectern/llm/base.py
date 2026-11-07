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
import re
from abc import ABC, abstractmethod
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .json_utils import extract_json, inline_schema

log = logging.getLogger("lectern.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when a model call fails after all retries. The message is shown to the user."""

    def __init__(self, message: str, *, retryable: bool = True, retry_after: float | None = None,
                 status: int | None = None, detail: str = ""):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after  # seconds the provider asked us to wait (429/503)
        self.status = status
        self.detail = detail


class LLMClient(ABC):
    provider: str
    model: str

    def __init__(self, *, provider: str, model: str, timeout: float = 420.0, max_retries: int = 4):
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
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise LLMError(
                        f"{self.provider} did not answer within {int(self.timeout)} s for '{task}'. "
                        "The model may be overloaded; retry this step, or raise LLM_TIMEOUT_SECONDS."
                    ) from exc
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise LLMError(f"Could not reach {self.provider} ({type(exc).__name__}). Check your connection and retry.") from exc
            backoff = min(2 ** attempt + random.uniform(0, 1), 30)
            wanted = getattr(last_error, "retry_after", None) or 0
            delay = min(max(backoff, wanted), 65)
            log.info("%s: attempt %d failed (%s); retrying in %.1fs", task, attempt, last_error, delay)
            await asyncio.sleep(delay)
        raise LLMError(str(last_error))  # pragma: no cover

    @abstractmethod
    async def _call(self, task, system, user, json_schema, temperature, max_tokens) -> dict: ...

    def http_timeout(self) -> httpx.Timeout:
        # A full lesson draft can take several minutes to generate, and a
        # non-streaming reply sends nothing until it is complete, so the read
        # timeout must cover the whole generation. Connecting should be quick.
        return httpx.Timeout(self.timeout, connect=20.0)


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value:
        try:
            return float(value)
        except ValueError:
            return None
    # Gemini puts the wait in the body: "retryDelay": "23s"
    match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', response.text or "")
    return float(match.group(1)) if match else None


def raise_for_status(provider: str, response: httpx.Response) -> None:
    code = response.status_code
    if code < 400:
        return
    detail = (response.text or "")[:400]
    if code == 401 or (code == 403 and "quota" not in detail.lower()):
        raise LLMError(f"{provider} rejected the API key ({code}). Check the key in your .env file.",
                       retryable=False, status=code, detail=detail)
    if code == 404:
        raise LLMError(f"{provider} does not recognise the model or endpoint (404): {detail}",
                       retryable=False, status=code, detail=detail)
    if code in (400, 422):
        raise LLMError(f"{provider} rejected the request ({code}): {detail}", retryable=False, status=code, detail=detail)
    if code in (429, 403):
        raise LLMError(f"{provider} rate limit or quota reached ({code}). Lectern waits and retries automatically.",
                       retry_after=_retry_after(response), status=code, detail=detail)
    raise LLMError(f"{provider} returned {code}: {detail}", retry_after=_retry_after(response), status=code, detail=detail)


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
