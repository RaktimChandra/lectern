import io
import zipfile

import httpx
import pytest

from lectern.main import create_app

from .conftest import ScriptedLLM, http_replies, make_toolkit

BODY = {
    "title": "HTTP Requests and Responses",
    "objective": "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
}


@pytest.fixture
async def client(settings, store):
    llm = ScriptedLLM(http_replies())
    app = create_app(settings, models=lambda: (llm, llm), toolkit=make_toolkit, store=store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.app = app
        yield c


async def created(client) -> dict:
    response = await client.post("/api/lessons", json=BODY)
    assert response.status_code == 201
    lesson = response.json()
    await client.app.state.services.runner.wait(lesson["id"])
    return (await client.get(f"/api/lessons/{lesson['id']}")).json()


async def test_health_has_no_secrets(client):
    data = (await client.get("/api/health")).json()
    assert data["lesson_minutes"] == 45
    assert "key" not in str(data).lower()


@pytest.mark.parametrize("body, field", [
    ({"title": "   ", "objective": BODY["objective"]}, "Lesson title"),
    ({"title": "HTTP basics", "objective": ""}, "Learning objective"),
    ({"title": "HTTP basics", "objective": "Learn HTTP"}, "full sentence"),
    ({**BODY, "seed_urls": ["ftp://nope"]}, "not a web address"),
])
async def test_validation_messages(client, body, field):
    response = await client.post("/api/lessons", json=body)
    assert response.status_code == 422
    assert field in response.json()["detail"]


async def test_create_list_read_delete(client):
    lesson = await created(client)
    assert lesson["version"] == 1 and lesson["content"]["sections"]
    assert all("text" not in s for s in lesson["sources"])
    listing = (await client.get("/api/lessons")).json()
    assert listing[0]["status"] == "ready" and listing[0]["accuracy_score"] is not None
    source = (await client.get(f"/api/lessons/{lesson['id']}/sources/S1")).json()
    assert source["passages"] and "idempotent" in " ".join(p["text"] for p in source["passages"])
    assert (await client.delete(f"/api/lessons/{lesson['id']}")).status_code == 204
    assert (await client.get(f"/api/lessons/{lesson['id']}")).status_code == 404


async def test_edit_conflict_and_restore(client):
    lesson = await created(client)
    lid = lesson["id"]
    ok = await client.put(f"/api/lessons/{lid}/sections/sec-2", json={"base_version": 1, "body_md": "Edited [S1]."})
    assert ok.status_code == 200 and ok.json()["version"] == 2
    assert ok.json()["versions"][-1]["reason"].startswith("Edited")
    stale = await client.put(f"/api/lessons/{lid}/sections/sec-2", json={"base_version": 1, "body_md": "Again."})
    assert stale.status_code == 409 and "changed since you opened it" in stale.json()["detail"]
    missing = await client.put(f"/api/lessons/{lid}/sections/sec-99", json={"base_version": 2, "body_md": "x"})
    assert missing.status_code == 404
    restored = await client.post(f"/api/lessons/{lid}/versions/1/restore", json={"base_version": 2})
    assert restored.json()["version"] == 3
    check = await client.put(f"/api/lessons/{lid}/checks/kc-1", json={"base_version": 3, "question": "What does GET do?",
                                                                     "options": ["Reads", "Writes"], "answer_index": 0, "explanation": "GET reads."})
    assert check.status_code == 200


async def test_preview_apply_dismiss_and_rerun_qc(client):
    lesson = await created(client)
    lid = lesson["id"]
    issue = next(i for i in lesson["fact_report"]["issues"] if i["category"] == "claim:contradicted")
    preview = (await client.post(f"/api/lessons/{lid}/issues/{issue['id']}/preview")).json()
    assert preview["method"] == "exact" and preview["base_version"] == 1
    applied = await client.post(f"/api/lessons/{lid}/issues/{issue['id']}/apply",
                                json={"base_version": 1, "after": preview["after"]})
    data = applied.json()
    assert data["version"] == 2
    assert next(i for i in data["fact_report"]["issues"] if i["id"] == issue["id"])["status"] == "applied"

    other = next(i for i in data["instruction_report"]["issues"] if i["status"] == "open")
    dismissed = (await client.post(f"/api/lessons/{lid}/issues/{other['id']}/dismiss", json={"reason": "Fine as is"})).json()
    assert next(i for i in dismissed["instruction_report"]["issues"] if i["id"] == other["id"])["status"] == "dismissed"

    rerun = await client.post(f"/api/lessons/{lid}/qc/facts")
    assert rerun.status_code == 202
    await client.app.state.services.runner.wait(lid)
    fresh = (await client.get(f"/api/lessons/{lid}")).json()
    assert fresh["fact_report"]["version"] == 2
    assert fresh["instruction_report"]["version"] == 1  # untouched, shown as out of date in the UI


async def test_export_formats(client):
    lesson = await created(client)
    lid = lesson["id"]
    md = await client.get(f"/api/lessons/{lid}/export?format=md")
    assert md.status_code == 200 and "## References" in md.text and "duration_minutes: 45" in md.text
    assert 'filename="http-requests-and-responses-v1.md"' in md.headers["content-disposition"]
    html = await client.get(f"/api/lessons/{lid}/export?format=html")
    assert "<details>" in html.text and "href=\"#ref-S1\"" in html.text
    z = await client.get(f"/api/lessons/{lid}/export?format=zip")
    names = set(zipfile.ZipFile(io.BytesIO(z.content)).namelist())
    assert {"lesson.md", "lesson.html", "references.md", "qc-facts-report.md", "qc-facts-report.json",
            "qc-teaching-report.md", "qc-teaching-report.json", "sources.json", "README.txt"} <= names
    bad = await client.get(f"/api/lessons/{lid}/export?format=pdf")
    assert bad.status_code == 400
