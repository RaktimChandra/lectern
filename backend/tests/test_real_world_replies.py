"""Replies shaped the way real models answer, not the way the schema is written.

These cases come from reviewing the pipeline against live provider behaviour:
nulls instead of defaults, capitalised enum values, over-long lists, numbering
from 1, Markdown page text from Tavily and passage ids echoed back as sources.
"""

from lectern.models import (
    ClaimJudgementsOut,
    DraftOut,
    InstructionReviewOut,
    ObjectiveAnalysisOut,
    OutlineOut,
)
from lectern.research.providers import markdown_to_text, parse_tavily

RUBRIC = ["objective_alignment", "clarity", "structure_and_flow", "examples_and_practice", "engagement", "accuracy_of_level"]


def test_nulls_and_enum_spelling_are_accepted():
    analysis = ObjectiveAnalysisOut.model_validate({
        "atoms": [{"id": "O1", "statement": "Explain GET", "verb": "explain", "bloom_level": "Understand", "key_terms": None}],
        "prerequisites": None, "misconceptions": ["POST is always secure"], "scope_notes": None,
    })
    assert analysis.atoms[0].bloom_level == "understand" and analysis.atoms[0].key_terms == []
    outline = OutlineOut.model_validate({"sections": [
        {"kind": "Hook", "title": "t", "minutes": 4, "atom_ids": ["O1"], "plan": "p"},
        {"kind": "concept", "title": "t", "minutes": 10, "atom_ids": ["O1"], "plan": "p"},
        {"kind": "Activity", "title": "t", "minutes": 10, "atom_ids": ["O1"], "plan": "p"},
        {"kind": "recap", "title": "t", "minutes": 3, "atom_ids": [], "plan": "p"},
    ]})
    assert [s.kind for s in outline.sections][:3] == ["hook", "concept", "activity"]


def test_reviewer_replies_tolerate_case_lists_and_scores():
    judged = ClaimJudgementsOut.model_validate({"judgements": [
        {"claim_index": 0, "verdict": "Partially Supported", "evidence": None, "note": None},
        {"claim_index": 1, "verdict": "supported", "evidence": [{"source_id": "S1", "quote": "q"}] * 5},
    ]})
    assert judged.judgements[0].verdict == "partially_supported" and judged.judgements[0].evidence == []
    assert len(judged.judgements[1].evidence) == 3
    review = InstructionReviewOut.model_validate({
        "rubric": [{"criterion": c, "score": 4.5 if i == 0 else 3, "rationale": "r"} for i, c in enumerate(RUBRIC)],
        "issues": [{"section_index": None, "category": "Engagement", "severity": "Critical", "title": "t",
                    "detail": "d", "suggestion": "s"}] * 16,
        "strengths": ["a", "b", "c", "d", "e", "f"],
    })
    assert review.rubric[0].score in (4, 5)
    assert len(review.issues) == 15 and review.issues[0].category == "engagement" and review.issues[0].severity == "high"
    assert len(review.strengths) == 5


def test_draft_accepts_null_instructor_notes():
    draft = DraftOut.model_validate({
        "summary": "s",
        "sections": [{"index": 0, "body_md": "b", "instructor_notes": None}],
        "knowledge_checks": [{"atom_ids": ["O1"], "question": f"q{i}", "options": ["a", "b", "c", "d"],
                              "answer_index": 0, "explanation": "e", "source_ids": None} for i in range(2)],
        "videos": None,
    })
    assert draft.sections[0].instructor_notes == "" and draft.videos == []


def test_tavily_markdown_is_reduced_to_plain_text_so_quotes_match():
    raw = ("The [GET](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/GET) method **requests** a "
           "representation of the specified resource. ![diagram](https://x.org/a.png)")
    assert markdown_to_text(raw) == "The GET method requests a representation of the specified resource. "
    hits = parse_tavily({"results": [{"url": "https://m.org", "title": "t", "content": "c", "raw_content": raw}]}, "q")
    assert "](" not in hits[0].content
