import httpx
import pytest

from lectern.main import create_app

from .conftest import ScriptedLLM, http_replies, make_toolkit

BODY = {
    "title": "HTTP Requests and Responses",
    "objective": "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
}


def app_with(settings, store, **overrides):
    for key, value in overrides.items():
        setattr(settings, key, value)
    llm = ScriptedLLM(http_replies())
    return create_app(settings, models=lambda: (llm, llm), toolkit=make_toolkit, store=store)


async def test_local_use_needs_no_passphrase_and_sends_security_headers(settings, store):
    app = app_with(settings, store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/api/lessons")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


async def test_passphrase_protects_the_api(settings, store):
    app = app_with(settings, store, access_token="correct horse")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/health")).json()["access_protected"] is True  # health stays open
        assert (await c.get("/api/lessons")).status_code == 401
        assert (await c.post("/api/auth", json={"token": "wrong"})).status_code == 401
        ok = await c.post("/api/auth", json={"token": "correct horse"})
        assert ok.status_code == 200
        assert "correct horse" not in ok.headers["set-cookie"]  # cookie holds a digest
        assert (await c.get("/api/lessons")).status_code == 200  # cookie now sent
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/lessons", headers={"X-Lectern-Key": "correct horse"})).status_code == 200


async def test_new_lessons_are_rate_limited(settings, store):
    app = app_with(settings, store, lessons_per_hour=2)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        codes = []
        for _ in range(3):
            response = await c.post("/api/lessons", json=BODY)
            codes.append(response.status_code)
            if response.status_code == 201:
                await app.state.services.runner.wait(response.json()["id"])
    assert codes == [201, 201, 429]
    assert int(response.headers["retry-after"]) > 0


async def test_oversized_requests_are_refused(settings, store):
    app = app_with(settings, store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/api/lessons", content=b"x" * 600_000, headers={"content-type": "application/json"})
    assert response.status_code == 413
