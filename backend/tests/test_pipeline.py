from lectern.events import EventBroker
from lectern.models import Lesson, LessonRequest, StepName
from lectern.pipeline import fixes
from lectern.pipeline.context import StepContext
from lectern.pipeline.runner import Runner, recover_interrupted

from .conftest import FakeWeb, ScriptedLLM, http_replies, make_toolkit

REQUEST = LessonRequest(
    title="HTTP Requests and Responses",
    objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
)


async def run_lesson(store, settings, llm, toolkit=None, reviewer=None) -> Lesson:
    runner = Runner(store, EventBroker(), settings, lambda: (llm, reviewer or llm), lambda: toolkit or make_toolkit())
    lesson = Lesson(id="l1", request=REQUEST)
    store.save(lesson)
    runner.start_from(lesson, None)
    await runner.wait("l1")
    return store.get("l1")


async def test_full_run_produces_cited_45_minute_lesson(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    assert all(s.status == "done" for s in lesson.steps), [(s.name, s.error) for s in lesson.steps]
    assert not lesson.running
    content = lesson.current.content
    assert lesson.version_number == 1 and lesson.current.reason == "Generated"
    assert content.total_minutes == 45
    assert [a.id for a in lesson.analysis.atoms] == ["O1", "O2", "O3", "O4"]
    # off-topic page dropped, sources ordered by reliability
    titles = [s.title for s in lesson.sources]
    assert "Cooking pasta" not in titles
    assert lesson.sources[0].reliability.tier == "primary"
    kinds = {s.kind for s in lesson.sources}
    assert {"web", "encyclopedia", "book", "video"} <= kinds
    video = next(s for s in lesson.sources if s.kind == "video")
    assert video.best_segment is not None and video.has_transcript
    # draft cleaning: unknown source id removed from question, non-video pick dropped
    assert all(sid != "S99" for k in content.knowledge_checks for sid in k.source_ids)
    assert [v.source_id for v in content.videos] == [video.id]
    assert lesson.research_plan.authoritative_domains == ["www.rfc-editor.org", "developer.mozilla.org"]


async def test_fact_layer_verifies_quotes_and_flags_contradiction(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    report = lesson.fact_report
    verdicts = {c.text[:20]: (c.verdict, c.downgraded) for c in report.claims}
    assert verdicts["The GET method reque"] == ("supported", False)
    assert verdicts["POST requests are id"] == ("contradicted", False)
    assert verdicts["A 5xx code means the"] == ("unsupported", True)  # invented quote downgraded
    assert len(report.claims) == 4  # the analogy is not checkable
    contradicted = next(i for i in report.issues if i.category == "claim:contradicted")
    assert contradicted.severity == "high"
    assert contradicted.fix.type == "replace" and contradicted.fix.find == "POST requests are idempotent"
    assert report.issues[0].severity == "high"
    assert 0 < report.accuracy_score < 1
    assert "of 4 checkable claims" in report.summary
    assert any(s.flags and "Bibliographic record only" in s.flags for s in report.sources)
    # holistic finding attached to the right section
    assert any(i.title == "3xx not mentioned" and i.section_id == "sec-5" for i in report.issues)


async def test_instruction_layer_measures_coverage_and_timing(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    report = lesson.instruction_report
    status = {r.atom_id: r.status for r in report.coverage}
    assert status["O1"] == "covered" and status["O4"] == "covered"
    assert status["O2"] == "taught_not_assessed"
    add = next(i for i in report.issues if i.atom_id == "O2")
    assert add.fix.type == "add_check"
    assert report.total_minutes == 45
    exact = next(i for i in report.issues if i.title == "Scenarios not listed")
    assert exact.fix.type == "replace"
    assert 0 < report.quality_score <= 100


async def test_research_failure_is_isolated(store, settings, llm):
    toolkit = make_toolkit(web=FakeWeb(fail_queries={"HTTP status code classes"}))
    lesson = await run_lesson(store, settings, llm, toolkit=toolkit)
    assert lesson.step(StepName.research).status == "done"
    failed = [e for e in lesson.research_log if not e.ok]
    assert any(e.query == "HTTP status code classes" for e in failed)
    assert any(line.level == "warn" and "503" in line.message for line in lesson.log)


async def test_no_readable_sources_fails_research_and_retry_keeps_earlier_work(store, settings, llm):
    toolkit = make_toolkit(web=None, wikipedia=None)
    lesson = await run_lesson(store, settings, llm, toolkit=toolkit)
    research = lesson.step(StepName.research)
    assert research.status == "failed" and "No readable sources" in research.error
    assert lesson.step(StepName.outline).status == "pending"
    assert lesson.analysis is not None and lesson.research_plan is not None

    calls_before = list(llm.calls)
    runner = Runner(store, EventBroker(), settings, lambda: (llm, llm), lambda: make_toolkit())
    runner.start_from(lesson, None)  # resumes from the failed step
    await runner.wait(lesson.id)
    lesson = store.get(lesson.id)
    assert all(s.status == "done" for s in lesson.steps)
    assert "analyze" not in llm.calls[len(calls_before):]  # earlier steps were not repeated


async def test_missing_model_key_fails_with_clear_message(store, settings):
    runner = Runner(store, EventBroker(), settings, lambda: (None, None), make_toolkit)
    lesson = Lesson(id="l2", request=REQUEST)
    store.save(lesson)
    runner.start_from(lesson, None)
    await runner.wait("l2")
    first = store.get("l2").step(StepName.analyze)
    assert first.status == "failed" and "No AI model is configured" in first.error


async def test_model_failure_is_recorded_and_retryable(store, settings):
    from lectern.llm.base import LLMError

    llm = ScriptedLLM(http_replies())
    llm.fail["draft"] = LLMError("Gemini rate limit reached (429). Wait a moment and retry.", retryable=False)
    lesson = await run_lesson(store, settings, llm)
    assert lesson.step(StepName.draft).status == "failed"
    assert "rate limit" in lesson.step(StepName.draft).error
    assert lesson.outline is not None and not lesson.versions


async def test_fixes_versions_and_restore(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    ctx = StepContext(lesson=lesson, settings=settings, writer=llm, reviewer=llm, toolkit=make_toolkit(), log=_noop)

    contradicted = next(i for i in lesson.all_issues() if i.category == "claim:contradicted")
    preview = await fixes.preview(ctx, contradicted)
    assert preview["method"] == "exact" and "POST requests are not idempotent" in preview["after"]
    fixes.apply(lesson, contradicted, after=preview["after"], check=None)
    assert lesson.version_number == 2 and contradicted.status == "applied" and contradicted.resolved_in_version == 2

    unsupported = next(i for i in lesson.all_issues() if i.category == "claim:unsupported")
    preview = await fixes.preview(ctx, unsupported)
    assert preview["method"] == "rewrite" and "not idempotent" in preview["after"]

    add = next(i for i in lesson.all_issues() if i.fix and i.fix.type == "add_check")
    preview = await fixes.preview(ctx, add)
    fixes.apply(lesson, add, after=None, check=preview["check"])
    assert len(lesson.current.content.knowledge_checks) == 3
    assert lesson.current.content.knowledge_checks[-1].atom_ids == ["O2"]

    fixes.edit_section(lesson, "sec-2", body_md="New text [S1].", title=None, minutes=12, instructor_notes=None, total_minutes=45)
    content = lesson.current.content
    assert content.section("sec-2").minutes == 12 and content.total_minutes == 45
    restored = fixes.restore(lesson, 1)
    assert restored.reason == "Restored version 1" and lesson.version_number == 5
    assert lesson.current.content.section("sec-2").body_md == lesson.versions[0].content.section("sec-2").body_md


async def test_apply_all_exact(store, settings, llm):
    lesson = await run_lesson(store, settings, llm)
    version, ids = fixes.apply_all_exact(lesson)
    assert version is not None and len(ids) >= 2
    assert "Read each of the eight scenarios" in lesson.current.content.section("sec-6").body_md


async def test_recover_interrupted(store, settings):
    lesson = Lesson(id="l3", request=REQUEST, running=True)
    lesson.step(StepName.research).status = "running"
    store.save(lesson)
    assert recover_interrupted(store) == 1
    restored = store.get("l3")
    assert restored.step(StepName.research).status == "failed" and not restored.running


async def _noop(*_):
    return None
