import pytest

from lectern.models import KnowledgeCheck, LessonContent, ObjectiveAtom, Section
from lectern.pipeline.checks import (
    cited_ids,
    coverage,
    match_quote,
    normalize_minutes,
    readability,
    section_timing,
    word_count,
)


@pytest.mark.parametrize("minutes", [[3, 9, 8, 7, 6, 7, 4, 1], [1, 1, 1, 1, 1], [40, 1, 1, 1, 1], [5, 5, 5, 5, 5, 5], [10, 20, 30]])
def test_minutes_always_sum_to_total(minutes):
    result = normalize_minutes(minutes, 45)
    assert sum(result) == 45
    assert min(result) >= 2
    assert len(result) == len(minutes)


def test_minutes_keep_proportions_roughly():
    result = normalize_minutes([10, 20, 30], 60, minimum=2)
    assert result[0] < result[1] < result[2]


def test_too_many_sections_for_time():
    with pytest.raises(ValueError):
        normalize_minutes([1] * 30, 45)


def test_citation_parsing():
    text = "GET is safe [S1]. POST is not [S1, S3]. Codes [S2; S4] and again [S1]."
    assert cited_ids(text) == ["S1", "S3", "S2", "S4"]


def test_word_count_ignores_code_and_citations():
    md = "Hello world [S1].\n\n```bash\ncurl -i https://example.org\n```\n"
    assert word_count(md) == 2


def test_quote_matching_exact_close_and_missing():
    source = "The GET method requests transfer of a current selected representation for the target resource."
    assert match_quote("the  GET method requests transfer of a current selected representation", source)[0] == "exact"
    assert match_quote("“The GET method requests transfer of a current selected representation”", "\"" + source + "\"")[0] == "exact"
    assert match_quote("The GET method request transfer of a current selected representation for the target", source)[0] == "close"
    assert match_quote("POST is always idempotent and safe for every server", source)[0] == "not_found"
    assert match_quote("anything at all here", "")[0] == "no_text"


def _section(kind, minutes, words, sid="sec-1"):
    return Section(id=sid, kind=kind, title="T", minutes=minutes, body_md=" ".join(["word"] * words))


def test_timing_status():
    assert section_timing(_section("concept", 5, 900), 180).status == "ok"
    assert section_timing(_section("concept", 2, 900), 180).status == "too_long"
    assert section_timing(_section("concept", 10, 50), 180).status == "too_short"
    assert section_timing(_section("activity", 8, 900), 180).status == "too_long"
    assert section_timing(_section("activity", 8, 200), 180).status == "ok"


def test_readability_reasonable():
    simple = readability("You send a request. The server sends a response. It has a status code.")
    assert simple["flesch_reading_ease"] > 60
    assert readability("```\ncode only\n```")["flesch_reading_ease"] is None


def test_coverage_statuses():
    atoms = [ObjectiveAtom(id=f"O{i}", statement=f"s{i}", verb="explain", bloom_level="understand") for i in (1, 2, 3, 4)]
    content = LessonContent(
        summary="x",
        sections=[
            Section(id="sec-1", kind="concept", title="a", minutes=10, atom_ids=["O1", "O2"], body_md="x"),
            Section(id="sec-2", kind="check", title="c", minutes=5, atom_ids=["O1", "O2", "O3", "O4"], body_md="x"),
        ],
        knowledge_checks=[
            KnowledgeCheck(id="kc-1", atom_ids=["O1"], question="q", options=["a", "b"], answer_index=0, explanation="e"),
            KnowledgeCheck(id="kc-2", atom_ids=["O3"], question="q", options=["a", "b"], answer_index=0, explanation="e"),
        ],
    )
    status = {row.atom_id: row.status for row in coverage(content, atoms)}
    assert status == {"O1": "covered", "O2": "taught_not_assessed", "O3": "assessed_not_taught", "O4": "missing"}
