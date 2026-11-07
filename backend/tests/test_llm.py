import httpx
import pytest
import respx
from pydantic import BaseModel

from lectern.llm.base import LLMError
from lectern.llm.json_utils import extract_json, inline_schema
from lectern.llm.providers import AnthropicClient, OpenAICompatibleClient
from lectern.models import DraftOut

from .conftest import ScriptedLLM


class Small(BaseModel):
    name: str
    count: int


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Here you go:\n```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('Sure. {"a": 3} Hope that helps.') == {"a": 3}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_inline_schema_removes_refs():
    schema = inline_schema(DraftOut.model_json_schema())
    assert "$defs" not in str(schema) and "$ref" not in str(schema)
    assert schema["properties"]["sections"]["items"]["properties"]["body_md"]["type"] == "string"


async def test_repairs_once_then_succeeds():
    replies = iter([{"name": "x"}, {"name": "x", "count": 2}])
    llm = ScriptedLLM({"t": lambda user: next(replies)})
    result = await llm.structured("t", system="s", user="u", schema=Small)
    assert result.count == 2 and llm.calls == ["t", "t"]


async def test_fails_after_second_bad_reply():
    llm = ScriptedLLM({"t": {"name": "x"}})
    with pytest.raises(LLMError, match="wrong shape"):
        await llm.structured("t", system="s", user="u", schema=Small)


@respx.mock
async def test_anthropic_forced_tool_call(monkeypatch):
    route = respx.post("https://api.anthropic.com/v1/messages").mock(return_value=httpx.Response(200, json={
        "content": [{"type": "tool_use", "name": "submit", "input": {"name": "ok", "count": 1}}], "stop_reason": "tool_use"}))
    client = AnthropicClient(api_key="k", model="m", timeout=5, max_retries=1)
    result = await client.structured("t", system="s", user="u", schema=Small)
    assert result.name == "ok"
    sent = route.calls[0].request
    assert sent.headers["x-api-key"] == "k"
    assert b'"tool_choice"' in sent.content


@respx.mock
async def test_retries_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr("lectern.llm.base.asyncio.sleep", _no_sleep)
    respx.post("https://api.openai.com/v1/chat/completions").mock(side_effect=[
        httpx.Response(429, json={"error": "slow down"}),
        httpx.Response(200, json={"choices": [{"message": {"content": '{"name": "n", "count": 3}'}, "finish_reason": "stop"}]}),
    ])
    client = OpenAICompatibleClient(provider="openai", api_key="k", base_url="https://api.openai.com/v1", model="m", timeout=5, max_retries=3)
    result = await client.structured("t", system="s", user="u", schema=Small)
    assert result.count == 3


@respx.mock
async def test_bad_key_is_not_retried(monkeypatch):
    monkeypatch.setattr("lectern.llm.base.asyncio.sleep", _no_sleep)
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=httpx.Response(401, json={}))
    client = OpenAICompatibleClient(provider="openai", api_key="bad", base_url="https://api.openai.com/v1", model="m", timeout=5, max_retries=3)
    with pytest.raises(LLMError, match="rejected the API key"):
        await client.structured("t", system="s", user="u", schema=Small)
    assert route.call_count == 1


@respx.mock
async def test_cut_off_reply_is_reported(monkeypatch):
    monkeypatch.setattr("lectern.llm.base.asyncio.sleep", _no_sleep)
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content": '{"name": '}, "finish_reason": "length"}]}))
    client = OpenAICompatibleClient(provider="openai", api_key="k", base_url="https://api.openai.com/v1", model="m", timeout=5, max_retries=2)
    with pytest.raises(LLMError, match="cut off"):
        await client.structured("t", system="s", user="u", schema=Small)


async def _no_sleep(_):
    return None


# --- Robustness against provider changes ------------------------------------

from lectern.llm import providers as llm_providers  # noqa: E402


def test_choose_model_prefers_newest_stable_flash():
    available = ["models/gemini-2.5-flash", "models/gemini-3.8-flash", "models/gemini-3.6-flash",
                 "models/gemini-3.8-flash-image", "models/gemini-3.5-flash-lite", "models/text-embedding-004"]
    assert llm_providers.choose_model("gemini", available) == "gemini-3.8-flash"
    assert llm_providers.choose_model("openai", ["gpt-4.1", "gpt-5.2", "gpt-5.2-mini", "whisper-1"]) == "gpt-5.2"
    assert llm_providers.choose_model("anthropic", ["claude-haiku-5-5", "claude-sonnet-5-5"]) == "claude-sonnet-5-5"


@respx.mock
async def test_unknown_model_is_replaced_from_the_model_list(monkeypatch):
    llm_providers._RESOLVED.clear()
    base = "https://generativelanguage.googleapis.com/v1beta/openai"
    respx.get(f"{base}/models").mock(return_value=httpx.Response(200, json={"data": [
        {"id": "models/gemini-3.8-flash"}, {"id": "models/gemini-3.8-flash-tts"}]}))
    sent_models = []

    def reply(request):
        model = __import__("json").loads(request.content)["model"]
        sent_models.append(model)
        if model == "gemini-retired":
            return httpx.Response(404, json={"error": "model not found"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"name": "n", "count": 1}'}, "finish_reason": "stop"}]})

    respx.post(f"{base}/chat/completions").mock(side_effect=reply)
    client = OpenAICompatibleClient(provider="gemini", api_key="k", base_url=base, model="gemini-retired", timeout=5, max_retries=1)
    result = await client.structured("t", system="s", user="u", schema=Small)
    assert result.count == 1
    assert sent_models == ["gemini-retired", "gemini-3.8-flash"]
    # The choice is remembered for clients built later in the same process.
    again = OpenAICompatibleClient(provider="gemini", api_key="k", base_url=base, model="gemini-retired", timeout=5, max_retries=1)
    assert again.model == "gemini-3.8-flash"
    llm_providers._RESOLVED.clear()


@respx.mock
async def test_adapts_when_a_model_rejects_max_tokens_and_temperature():
    seen = []

    def reply(request):
        body = __import__("json").loads(request.content)
        seen.append(sorted(body))
        if "max_tokens" in body:
            return httpx.Response(400, json={"error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."}})
        if "temperature" in body:
            return httpx.Response(400, json={"error": {"message": "Unsupported value: 'temperature' does not support 0.2"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"name": "n", "count": 4}'}, "finish_reason": "stop"}]})

    respx.post("https://api.openai.com/v1/chat/completions").mock(side_effect=reply)
    client = OpenAICompatibleClient(provider="openai", api_key="k", base_url="https://api.openai.com/v1", model="m", timeout=5, max_retries=1)
    result = await client.structured("t", system="s", user="u", schema=Small)
    assert result.count == 4
    assert "max_completion_tokens" in seen[-1] and "temperature" not in seen[-1]
    # Later calls start from the adapted request.
    await client.structured("t", system="s", user="u", schema=Small)
    assert len(seen) == 4


@respx.mock
async def test_waits_as_long_as_the_provider_asks(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("lectern.llm.base.asyncio.sleep", fake_sleep)
    respx.post("https://api.openai.com/v1/chat/completions").mock(side_effect=[
        httpx.Response(429, headers={"retry-after": "17"}, json={}),
        httpx.Response(200, json={"choices": [{"message": {"content": '{"name": "n", "count": 5}'}, "finish_reason": "stop"}]}),
    ])
    client = OpenAICompatibleClient(provider="openai", api_key="k", base_url="https://api.openai.com/v1", model="m", timeout=5, max_retries=3)
    assert (await client.structured("t", system="s", user="u", schema=Small)).count == 5
    assert waits and waits[0] >= 17
