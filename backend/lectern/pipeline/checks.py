"""Deterministic checks. These run in code, so their results never depend on a model.

They cover the things a model is bad at judging about its own output: whether
the minutes add up, whether every cited source exists, whether a quoted piece
of evidence really appears in the source, how long a section takes to read.
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from ..models import LessonContent, ObjectiveAtom, QuoteMatch, Section, SectionTiming

CITATION = re.compile(r"\[(S\d+(?:\s*[,;]\s*S\d+)*)\]")
CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
MD_NOISE = re.compile(r"[#>*_\-|\[\]()!]+")


# ---------------------------------------------------------------------------
# Time budget
# ---------------------------------------------------------------------------


def normalize_minutes(minutes: list[int], total: int, minimum: int = 2) -> list[int]:
    """Scale section minutes so they sum to exactly `total`.

    Uses the largest-remainder method so rounding never loses or gains a minute,
    and gives every section at least `minimum` minutes.
    """
    if not minutes:
        return []
    if minimum * len(minutes) > total:
        raise ValueError("too many sections for the time available")
    raw = [max(m, 1) for m in minutes]
    spare = total - minimum * len(raw)
    weight = sum(raw)
    shares = [spare * m / weight for m in raw]
    floors = [int(s) for s in shares]
    leftover = spare - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: shares[i] - floors[i], reverse=True)
    for i in order[:leftover]:
        floors[i] += 1
    return [minimum + f for f in floors]


# ---------------------------------------------------------------------------
# Text measures
# ---------------------------------------------------------------------------


def prose_text(markdown: str) -> str:
    text = CODE_FENCE.sub(" ", markdown)
    text = INLINE_CODE.sub(" code ", text)
    text = CITATION.sub(" ", text)
    text = MD_NOISE.sub(" ", text)
    return " ".join(text.split())


def code_lines(markdown: str) -> int:
    return sum(block.count("\n") - 1 for block in CODE_FENCE.findall(markdown))


def word_count(markdown: str) -> int:
    return sum(1 for token in prose_text(markdown).split() if any(ch.isalnum() for ch in token))


def estimate_minutes(section: Section, wpm: int) -> float:
    """Reading time plus a little time per line of code to read it properly."""
    words = word_count(section.body_md) + word_count(section.instructor_notes) * 0  # notes are for the instructor
    return round(words / wpm + code_lines(section.body_md) * 0.12, 1)


def section_timing(section: Section, wpm: int) -> SectionTiming:
    estimate = estimate_minutes(section, wpm)
    allotted = section.minutes
    if section.kind in ("activity", "check"):
        # Allotted time is mostly for doing; reading should leave room for it.
        status = "too_long" if estimate > allotted * 0.6 else "ok"
    else:
        if estimate > allotted * 1.3 + 0.5:
            status = "too_long"
        elif allotted >= 4 and estimate < allotted * 0.3:
            status = "too_short"
        else:
            status = "ok"
    return SectionTiming(
        section_id=section.id, allotted_minutes=allotted, estimated_minutes=estimate,
        words=word_count(section.body_md), status=status,
    )


def _syllables(word: str) -> int:
    word = word.lower()
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", word)))


def readability(markdown: str) -> dict:
    """Flesch reading ease and sentence stats for the prose (code excluded)."""
    text = prose_text(markdown)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 3]
    words = text.split()
    if not sentences or not words:
        return {"flesch_reading_ease": None, "avg_sentence_words": 0, "long_sentences": 0, "words": len(words)}
    syllables = sum(_syllables(w) for w in words)
    avg_sentence = len(words) / len(sentences)
    flesch = 206.835 - 1.015 * avg_sentence - 84.6 * (syllables / len(words))
    return {
        "flesch_reading_ease": round(flesch, 1),
        "avg_sentence_words": round(avg_sentence, 1),
        "long_sentences": sum(1 for s in sentences if len(s.split()) > 30),
        "words": len(words),
    }


def readability_band(score: float | None) -> str:
    if score is None:
        return "not enough prose to score"
    if score >= 60:
        return "plain English"
    if score >= 45:
        return "fairly technical"
    if score >= 30:
        return "dense"
    return "very dense"


# ---------------------------------------------------------------------------
# Citations and evidence
# ---------------------------------------------------------------------------


def cited_ids(markdown: str) -> list[str]:
    ids: list[str] = []
    for group in CITATION.findall(markdown):
        for part in re.split(r"[,;]", group):
            part = part.strip()
            if part and part not in ids:
                ids.append(part)
    return ids


def lesson_cited_ids(content: LessonContent) -> list[str]:
    ids: list[str] = []
    for section in content.sections:
        for sid in cited_ids(section.body_md):
            if sid not in ids:
                ids.append(sid)
    for check in content.knowledge_checks:
        for sid in check.source_ids:
            if sid not in ids:
                ids.append(sid)
    return ids


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def match_quote(quote: str, source_text: str) -> tuple[QuoteMatch, float]:
    """Does the quoted evidence really appear in the source?

    `exact`: appears verbatim (after normalising whitespace, quotes and case).
    `close`: a near-verbatim match (minor punctuation or word differences).
    `not_found`: the reviewer's quote is not in the source, so it cannot count.
    """
    if not source_text:
        return "no_text", 0.0
    q, s = _normalize(quote).strip("\"' "), _normalize(source_text)
    if len(q) < 12:
        return "not_found", 0.0
    if q in s:
        return "exact", 100.0
    score = fuzz.partial_ratio(q, s) if len(q) <= 600 else 0.0
    if score >= 90:
        return "close", round(score, 1)
    return "not_found", round(score, 1)


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def coverage(content: LessonContent, atoms: list[ObjectiveAtom]):
    from ..models import CoverageRow

    rows = []
    for atom in atoms:
        taught = [s.id for s in content.sections if atom.id in s.atom_ids and s.kind not in ("check", "recap")]
        assessed = [k.id for k in content.knowledge_checks if atom.id in k.atom_ids]
        if taught and assessed:
            status = "covered"
        elif taught:
            status = "taught_not_assessed"
        elif assessed:
            status = "assessed_not_taught"
        else:
            status = "missing"
        rows.append(CoverageRow(atom_id=atom.id, statement=atom.statement, taught_in=taught, assessed_in=assessed, status=status))
    return rows
