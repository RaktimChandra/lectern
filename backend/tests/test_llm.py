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
