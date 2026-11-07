"""Regression tests for defects found in the independent code review."""

import pytest

from lectern.models import ClaimJudgementOut, ClaimJudgementsOut, Lesson, LessonRequest, Reliability, Source, StepName
from lectern.pipeline import fixes
from lectern.pipeline.context import StepError
from lectern.pipeline.runner import merge_concurrent
from lectern.research.passages import PassageIndex
from lectern.research.providers import ResearchError, ensure_public_url

from .test_pipeline import run_lesson


async def test_blank_option_does_not_shift_the_correct_answer(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    fixes.edit_check(lesson, "kc-1", question="Pick one", options=["Alpha", "", "Gamma", "Delta"], answer_index=2, explanation="Gamma.")
    check = lesson.current.content.knowledge_checks[0]
    assert check.options == ["Alpha", "Gamma", "Delta"] and check.options[check.answer_index] == "Gamma"
    with pytest.raises(ValueError):
        fixes.edit_check(lesson, "kc-1", question="Pick one", options=["Alpha", "", "Gamma"], answer_index=1, explanation="")


async def test_fix_cannot_be_applied_twice_or_with_wrong_payload(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    add = next(i for i in lesson.all_issues() if i.fix and i.fix.type == "add_check")
    check = {"atom_ids": ["O2"], "question": "Q?", "options": ["a", "b", "c"], "answer_index": 0, "explanation": "Because a."}
    with pytest.raises(StepError):
        fixes.apply(lesson, add, after="text", check=None)
    fixes.apply(lesson, add, after=None, check=check)
    with pytest.raises(StepError, match="already been applied"):
        fixes.apply(lesson, add, after=None, check=check)


def test_search_works_with_one_small_source():
    source = Source(id="S1", kind="instructor", title="404", url="https://x.org", text="The 404 Not Found status means the server cannot find the requested resource.",
                    reliability=Reliability(tier="unknown", score=0.5))
    index = PassageIndex.from_sources([source])
    assert index.search("HTTP 404 resource", k=3)
    assert index.search("HTTP 404 resource", k=3, prefer_sources=["S1"])[0][0].source_id == "S1"


async def test_renumbered_judgement_batches_are_matched_by_position(store, settings, llm):
    from lectern.pipeline import qc_facts
    from lectern.pipeline.context import StepContext
    from lectern.models import ClaimOut

    from .conftest import ScriptedLLM, make_toolkit

    claims = [ClaimOut(section_index=0, text=f"claim {i}", cited_source_ids=[]) for i in range(8)]

    def judge(user):
        count = user.count("Claim ")
        return ClaimJudgementsOut(judgements=[ClaimJudgementOut(claim_index=i + 1, verdict="unsupported") for i in range(count)]).model_dump()

    model = ScriptedLLM({"judge_claims": judge})
    lesson = await run_lesson(store, settings, llm)
    ctx = StepContext(lesson=lesson, settings=settings, writer=model, reviewer=model, toolkit=make_toolkit(), log=None)
    out = await qc_facts._judge(ctx, claims, [[] for _ in claims])
    assert sorted(out) == list(range(1, 9))


async def test_rerun_of_generation_step_keeps_edits(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    worked = lesson.model_copy(deep=True)
    fixes.edit_section(lesson, "sec-1", body_md="Edited by the instructor.", title=None, minutes=None, instructor_notes=None, total_minutes=45)
    merged = merge_concurrent(worked, lesson, StepName.outline)
    assert merged.version_number == 2 and merged.current.content.section("sec-1").body_md == "Edited by the instructor."


@pytest.mark.parametrize("url", ["http://127.0.0.1/admin", "http://169.254.169.254/latest", "http://10.0.0.5/", "ftp://example.org"])
async def test_private_addresses_are_refused(url):
    with pytest.raises(ResearchError):
        await ensure_public_url(url)


async def test_blank_section_edit_rejected_and_unknown_api_path_404(settings, store):
    import httpx

    from lectern.main import FRONTEND_DIST, create_app

    from .conftest import ScriptedLLM, http_replies, make_toolkit

    llm = ScriptedLLM(http_replies())
    app = create_app(settings, models=lambda: (llm, llm), toolkit=make_toolkit, store=store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/lessons", json={"title": "HTTP Requests and Responses", "objective": "Explain GET and POST methods and status code classes."})
        lid = r.json()["id"]
        await app.state.services.runner.wait(lid)
        blank = await c.put(f"/api/lessons/{lid}/sections/sec-1", json={"base_version": 1, "body_md": "   "})
        assert blank.status_code == 422
        if FRONTEND_DIST.exists():
            assert (await c.get("/api/does-not-exist")).status_code == 404
