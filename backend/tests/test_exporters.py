from lectern import exporters
from lectern.events import EventBroker
from lectern.models import Lesson, LessonRequest
from lectern.pipeline.runner import Runner

from .conftest import make_toolkit


async def finished(store, settings, llm) -> Lesson:
    req = LessonRequest(title="HTTP Requests and Responses",
                        objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.")
    runner = Runner(store, EventBroker(), settings, lambda: (llm, llm), make_toolkit)
    lesson = Lesson(id="e1", request=req)
    store.save(lesson)
    runner.start_from(lesson, None)
    await runner.wait("e1")
    return store.get("e1")


async def test_markdown_has_every_part(store, settings, llm):
    lesson = await finished(store, settings, llm)
    md = exporters.lesson_markdown(lesson)
    for section in lesson.current.content.sections:
        assert section.title in md
    assert "**Question 1.**" in md and "## Answer key" in md and "## Watch next" in md
    refs = md.split("## References")[1]
    cited = {s.id for s in exporters.cited_sources(lesson, lesson.current.content)}
    for source in lesson.sources:
        assert (f"[{source.id}]" in refs) == (source.id in cited)
    assert "Watch " in md  # video segment


async def test_html_escapes_and_is_standalone(store, settings, llm):
    lesson = await finished(store, settings, llm)
    lesson.current.content.sections[0].body_md = "<script>alert(1)</script> Hello [S1]"
    html = exporters.lesson_html(lesson)
    assert "<script>alert" not in html
    assert "<link" not in html and "src=" not in html


async def test_reports_mark_stale_versions(store, settings, llm):
    lesson = await finished(store, settings, llm)
    from lectern.pipeline import fixes

    fixes.edit_section(lesson, "sec-1", body_md="Changed.", title=None, minutes=None, instructor_notes=None, total_minutes=45)
    text = exporters.facts_report_markdown(lesson, lesson.fact_report)
    assert "has changed since (now version 2)" in text
    teaching = exporters.instruction_report_markdown(lesson, lesson.instruction_report)
    assert "## Objective coverage" in teaching and "## Rubric" in teaching


def test_reference_formats():
    from lectern.models import Reliability, Source, VideoSegment

    rel = Reliability(tier="publisher", score=0.8)
    book = Source(id="S5", kind="book", title="HTTP: The Definitive Guide", url="https://b.example", authors=["D. Gourley"],
                  year=2002, publisher="O'Reilly Media", isbn="9781565925090", reliability=rel)
    assert exporters.reference_text(book).startswith("D. Gourley. (2002). HTTP: The Definitive Guide. O'Reilly Media. ISBN 9781565925090.")
    video = Source(id="S6", kind="video", title="HTTP", url="https://youtu.be/x", channel="C", duration_seconds=640,
                   best_segment=VideoSegment(start_seconds=130, end_seconds=400, excerpt="x"), reliability=rel)
    assert "Most relevant part: 2:10 to 6:40." in exporters.reference_text(video)
    assert exporters.slug("HTTP Requests & Responses!") == "http-requests-responses"
