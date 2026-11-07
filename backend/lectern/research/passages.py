"""Split source text into passages and rank them with BM25.

Passages are what the QC fact checker actually reads: for each claim, the
best-matching passages across all sources are handed to the reviewer model,
which must quote from them. Ranking is lexical (BM25), so it is fast,
deterministic and needs no embedding API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")

STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has have how i if in into is it its
    just may more most no not of on or our out so than that the their them then there these they this those to
    too up us was we were what when where which while who why will with would you your about also any each
    other such only own same very s t""".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def chunk(text: str, target_chars: int = 900, overlap_sentences: int = 1) -> list[str]:
    """Group sentences into passages of roughly `target_chars`, keeping paragraph boundaries where possible."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences: list[str] = []
    for para in paragraphs:
        sentences.extend(split_sentences(" ".join(para.split())))
    passages: list[str] = []
    current: list[str] = []
    fresh = 0  # sentences in `current` not yet included in any passage
    size = 0
    for sentence in sentences:
        current.append(sentence)
        fresh += 1
        size += len(sentence) + 1
        if size >= target_chars:
            passages.append(" ".join(current))
            current = current[-overlap_sentences:] if overlap_sentences else []
            fresh = 0
            size = sum(len(s) + 1 for s in current)
    if fresh:
        new_part = " ".join(current[-fresh:])
        if passages and len(new_part) < target_chars // 4:
            passages[-1] = f"{passages[-1]} {new_part}"
        else:
            passages.append(" ".join(current))
    return passages


@dataclass(frozen=True)
class Passage:
    id: str
    source_id: str
    text: str


class PassageIndex:
    def __init__(self, passages: list[Passage]):
        self.passages = passages
        tokenized = [tokenize(p.text) or ["_"] for p in passages]
        self._tokens = [set(t) for t in tokenized]
        self._bm25 = BM25Okapi(tokenized) if passages else None

    @classmethod
    def from_sources(cls, sources) -> "PassageIndex":
        passages: list[Passage] = []
        for source in sources:
            body = source.text or source.snippet
            if not body:
                continue
            for i, text in enumerate(chunk(body), start=1):
                passages.append(Passage(id=f"{source.id}.p{i}", source_id=source.id, text=text))
        return cls(passages)

    def search(self, query: str, k: int = 6, prefer_sources: list[str] | None = None) -> list[tuple[Passage, float]]:
        if not self._bm25:
            return []
        terms = tokenize(query)
        if not terms:
            return []
        scores = self._bm25.get_scores(terms)
        wanted = set(terms)
        # BM25Okapi can score a common term at or below zero when the corpus is tiny (one or two
        # sources), so relevance is "shares a query term", and the score only orders the results.
        ranked = sorted(
            ((p, float(s)) for p, s, toks in zip(self.passages, scores, self._tokens) if toks & wanted),
            key=lambda pair: pair[1], reverse=True,
        )
        results = ranked[: k * 3]
        if prefer_sources:
            # Make sure each cited source contributes its best passage, so the checker sees what was cited.
            preferred = []
            for source_id in prefer_sources:
                best = next(((p, s) for p, s in ranked if p.source_id == source_id), None)
                if best and best not in preferred:
                    preferred.append(best)
            rest = [r for r in results if r not in preferred]
            results = preferred + rest
        return results[:k]


def relevance(text: str, terms: list[str]) -> float:
    """How much of the topic's vocabulary appears in the text (0..1).

    The denominator is capped so a page that covers part of a broad lesson well
    (say, only status codes) is not punished for missing the other half.
    """
    if not terms:
        return 1.0
    tokens = set(tokenize(text))
    wanted = {t for term in terms for t in tokenize(term)}
    if not wanted:
        return 1.0
    return min(1.0, len(tokens & wanted) / min(len(wanted), 8))
