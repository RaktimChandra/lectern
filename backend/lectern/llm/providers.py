"""Concrete clients: Anthropic Messages API and any OpenAI-compatible chat API."""

from __future__ import annotations

import json

import httpx

from ..config import OPENAI_COMPATIBLE_BASE_URLS, Settings
from .base import LLMClient, LLMError, parse_json_text, raise_for_status


class AnthropicClient(LLMClient):
    endpoint = "https://api.anthropic.com/v1/messages"

    def __init__(self, *, api_key: str, **kwargs):
        super().__init__(provider="anthropic", **kwargs)
        self._api_key = api_key

    async def _call(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
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
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=body, headers=headers)
        raise_for_status("Anthropic", response)
        data = response.json()
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return block.get("input") or {}
        if data.get("stop_reason") == "max_tokens":
            raise LLMError("Anthropic reply was cut off (max_tokens). Retry, or use a model with a larger output limit.")
        raise LLMError("Anthropic reply did not contain the structured result.")


class OpenAICompatibleClient(LLMClient):
    def __init__(self, *, provider: str, api_key: str, base_url: str, **kwargs):
        super().__init__(provider=provider, **kwargs)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def _call(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
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
        headers = {"Authorization": f"Bearer {self._api_key}", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self._base_url}/chat/completions", json=body, headers=headers)
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
    return OpenAICompatibleClient(
        provider=provider, api_key=key, base_url=OPENAI_COMPATIBLE_BASE_URLS[provider], **common
    )
