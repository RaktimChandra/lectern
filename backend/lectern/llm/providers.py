"""Concrete clients: Anthropic Messages API and any OpenAI-compatible chat API.

Two pieces of robustness live here because provider APIs change faster than
this project does:

* Model discovery. If the configured model is unknown (404), the client lists
  the models the key can use and picks the best match for the provider, then
  remembers that choice for the rest of the process. A retired default model
  therefore costs one extra request instead of a failed lesson.
* Parameter adaptation. Newer OpenAI-compatible models reject some classic
  parameters (`max_tokens`, a custom `temperature`, `reasoning_effort`). When a
  400 names one of them, the request is adjusted and sent again.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from ..config import OPENAI_COMPATIBLE_BASE_URLS, Settings
from .base import LLMClient, LLMError, parse_json_text, raise_for_status

log = logging.getLogger("lectern.llm")

# (provider, configured model) -> model actually used after discovery.
_RESOLVED: dict[tuple[str, str], str] = {}


def resolved_model(provider: str, model: str) -> str:
    return _RESOLVED.get((provider, model), model)


def _version_key(text: str) -> tuple[float, ...]:
    return tuple(float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)[:2]) or (0.0,)


def choose_model(provider: str, available: list[str]) -> str | None:
    """Pick the best general-purpose text model from a provider's model list."""
    ids = [a.removeprefix("models/") for a in available if a]
    skip = re.compile(r"image|tts|audio|live|vision|embed|transcribe|search|realtime|instruct|codex|moderation|whisper|dall|babbage|davinci|robotics|computer-use|native", re.I)
    ids = [i for i in ids if not skip.search(i)]
    if provider == "gemini":
        stable = [i for i in ids if re.fullmatch(r"gemini-\d+(?:\.\d+)?-flash", i)]
        if stable:
            return max(stable, key=_version_key)
        for wanted in ("gemini-flash-latest", "gemini-pro-latest"):
            if wanted in ids:
                return wanted
        flash = [i for i in ids if i.startswith("gemini-") and "flash" in i and "lite" not in i]
        return max(flash, key=_version_key) if flash else None
    if provider == "openai":
        plain = [i for i in ids if re.fullmatch(r"gpt-\d+(?:\.\d+)?", i)]
        if plain:
            return max(plain, key=_version_key)
        gpt = [i for i in ids if i.startswith("gpt-") and "mini" not in i and "nano" not in i]
        return max(gpt, key=_version_key) if gpt else None
    if provider == "anthropic":
        for family in ("sonnet", "opus", "haiku"):
            matches = [i for i in ids if family in i]
            if matches:
                return max(matches, key=_version_key)
        return None
    if provider == "openrouter":
        for family in ("anthropic/claude-sonnet", "google/gemini", "openai/gpt"):
            matches = [i for i in ids if i.startswith(family) and ":" not in i]
            if matches:
                return max(matches, key=_version_key)
        return None
    return ids[0] if ids else None


class _DiscoveringClient(LLMClient):
    """Shared 404 handling: list models once, pick a replacement, retry."""

    async def _list_models(self) -> list[str]:  # pragma: no cover - provider specific
        raise NotImplementedError

    async def _call(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
        try:
            return await self._send(task, system, user, json_schema, temperature, max_tokens)
        except LLMError as exc:
            if exc.status != 404 or (self.provider, self.configured_model) in _RESOLVED:
                raise
            try:
                available = await self._list_models()
            except Exception as list_error:  # noqa: BLE001 - keep the original, clearer error
                log.warning("could not list %s models: %s", self.provider, list_error)
                raise exc
            choice = choose_model(self.provider, available)
            if not choice or choice == self.model:
                raise LLMError(
                    f"{self.provider} does not offer the model '{self.model}', and no replacement was found. "
                    f"Set LLM_MODEL / QC_MODEL in .env to one of: {', '.join(available[:12])}",
                    retryable=False,
                ) from exc
            log.warning("%s model '%s' is unavailable; using '%s' instead", self.provider, self.model, choice)
            _RESOLVED[(self.provider, self.configured_model)] = choice
            self.model = choice
            return await self._send(task, system, user, json_schema, temperature, max_tokens)

    async def _send(self, task, system, user, json_schema, temperature, max_tokens) -> dict:  # pragma: no cover
        raise NotImplementedError


class AnthropicClient(_DiscoveringClient):
    endpoint = "https://api.anthropic.com/v1/messages"

    def __init__(self, *, api_key: str, model: str, **kwargs):
        super().__init__(provider="anthropic", model=resolved_model("anthropic", model), **kwargs)
        self.configured_model = model
        self._api_key = api_key
        self._drop_temperature = False

    def _headers(self) -> dict:
        return {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    async def _list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.anthropic.com/v1/models", params={"limit": 100}, headers=self._headers())
        raise_for_status("Anthropic", response)
        return [m.get("id", "") for m in response.json().get("data", [])]

    async def _send(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
        # Forcing a single tool call is Anthropic's most reliable way to get schema-shaped JSON.
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [
                {
                    "name": "submit",
                    "description": f"Submit the result for: {task}",
                    "input_schema": json_schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": "submit"},
        }
        if self._drop_temperature:
            body.pop("temperature")
        async with httpx.AsyncClient(timeout=self.http_timeout()) as client:
            response = await client.post(self.endpoint, json=body, headers=self._headers())
            if response.status_code == 400 and "temperature" in response.text and not self._drop_temperature:
                # Some newer models fix their own sampling settings.
                self._drop_temperature = True
                body.pop("temperature")
                response = await client.post(self.endpoint, json=body, headers=self._headers())
        if response.status_code == 529:  # Anthropic "overloaded": retry like a 503
            raise LLMError("Anthropic is overloaded (529). Lectern waits and retries automatically.", status=529)
        raise_for_status("Anthropic", response)
        data = response.json()
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return block.get("input") or {}
        if data.get("stop_reason") == "max_tokens":
            raise LLMError("Anthropic reply was cut off (max_tokens). Retry, or use a model with a larger output limit.")
        raise LLMError("Anthropic reply did not contain the structured result.")


# Parameters a newer model may refuse, and how to adapt when the 400 names them.
_ADAPTATIONS = (
    ("max_tokens", lambda b: b.update(max_completion_tokens=b.pop("max_tokens"))),
    ("reasoning_effort", lambda b: b.pop("reasoning_effort", None)),
    ("reasoning", lambda b: b.pop("reasoning_effort", None)),
    ("temperature", lambda b: b.pop("temperature", None)),
    ("response_format", lambda b: b.pop("response_format", None)),
)


class OpenAICompatibleClient(_DiscoveringClient):
    def __init__(self, *, provider: str, api_key: str, base_url: str, model: str, **kwargs):
        super().__init__(provider=provider, model=resolved_model(provider, model), **kwargs)
        self.configured_model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._adapt: list[str] = []  # parameter fixes learned from earlier 400s, reused on later calls

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}", "content-type": "application/json"}

    async def _list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self._base_url}/models", headers=self._headers())
        raise_for_status(self.provider.capitalize(), response)
        return [m.get("id", "") for m in response.json().get("data", [])]

    def _body(self, system: str, user: str, json_schema: dict, temperature: float, max_tokens: int) -> dict:
        schema_text = json.dumps(json_schema, ensure_ascii=False)
        system_with_schema = (
            f"{system}\n\nReply with a single JSON object only, no prose, matching this JSON Schema:\n{schema_text}"
        )
        body = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user},
            ],
        }
        if self.provider == "gemini":
            # Gemini 2.5+ models think before answering, and thinking shares the
            # output budget. Low effort keeps structured steps fast and avoids
            # truncated JSON. Dropped automatically if a model refuses it.
            body["reasoning_effort"] = "low"
        for name in self._adapt:
            for param, fix in _ADAPTATIONS:
                if param == name and param in body:
                    fix(body)
        return body

    async def _send(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
        body = self._body(system, user, json_schema, temperature, max_tokens)
        async with httpx.AsyncClient(timeout=self.http_timeout()) as client:
            for _ in range(len(_ADAPTATIONS) + 1):
                response = await client.post(f"{self._base_url}/chat/completions", json=body, headers=self._headers())
                if response.status_code != 400:
                    break
                text = response.text.lower()
                if "api key not valid" in text or "api_key_invalid" in text:
                    raise LLMError(f"{self.provider} rejected the API key. Check the key in your .env file.", retryable=False)
                fix = next(((p, f) for p, f in _ADAPTATIONS if p in text and p in body and p not in self._adapt), None)
                if fix is None:
                    break
                log.info("%s rejected '%s' for %s; adapting the request", self.provider, fix[0], self.model)
                self._adapt.append(fix[0])
                fix[1](body)
        raise_for_status(self.provider.capitalize(), response)
        data = response.json()
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.provider} reply had an unexpected shape.") from exc
        if choice.get("finish_reason") == "length":
            raise LLMError(f"{self.provider} reply was cut off (length limit). Retry or raise max_tokens.")
        return parse_json_text(self.provider, content or "")


def build_client(provider: str, model: str, settings: Settings) -> LLMClient:
    common = {"model": model, "timeout": settings.llm_timeout_seconds, "max_retries": settings.llm_max_retries}
    key = settings.key_for(provider)
    if not key:
        raise LLMError(f"No API key configured for {provider}.", retryable=False)
    if provider == "anthropic":
        return AnthropicClient(api_key=key, **common)
    base_url = settings.ollama_base_url if provider == "ollama" else OPENAI_COMPATIBLE_BASE_URLS[provider]
    return OpenAICompatibleClient(provider=provider, api_key=key, base_url=base_url, **common)
