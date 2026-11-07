"""QC Layer 1: research and factual accuracy.

The reviewer model extracts claims and judges each one against retrieved
passages, but it never has the last word: code checks that every quoted piece
of evidence really appears in the fetched source, and lowers the verdict when it
does not. Citation integrity and source reliability are checked in code only.
"""

from __future__ import annotations

import asyncio
import re

from ..models import (
    ClaimCheck,
    ClaimJudgementOut,
    ClaimJudgementsOut,
    ClaimOut,
    ClaimsOut,
    Evidence,
    FactReport,
    FactReviewOut,
    Fix,
    Issue,
    LessonContent,
    SourceAssessment,
)
from ..research.passages import PassageIndex, relevance
from . import prompts
from .checks import cited_ids, lesson_cited_ids, match_quote
from .context import StepContext, StepError, source_label

MAX_CLAIMS = 30
BATCH = 6
WEAK_SOURCE = 0.55

DOWNGRADE_NOTE = "The reviewer's evidence could not be found in the source text, so this claim is treated as unsupported."


def locate(text: str, body: str) -> str | None:
    """Return the exact substring of `body` matching `text` case-insensitively, if present."""
    if not text:
        return None
    pattern = re.escape(text.strip().rstrip("."))
    match = re.search(pattern, body, flags=re.IGNORECASE)
    return match.group(0) if match else None


async def run(ctx: StepContext) -> str:
    lesson = ctx.lesson
    if lesson.current is None:
        raise StepError("There is no lesson to check yet. Retry from 'Write the lesson'.")
    reviewer = ctx.require_reviewer()
    content = lesson.current.content
    version = lesson.version_number

    # 1. Claims
    system, user = prompts.extract_claims(content)
    extracted = await reviewer.structured("extract_claims", system=system, user=user, schema=ClaimsOut, temperature=0.0)
    claims = [c for c in extracted.claims if c.checkable and 0 <= c.section_index < len(content.sections)][:MAX_CLAIMS]
    await ctx.log(f"Found {len(claims)} checkable claims.", "info")

    # 2-4. Evidence and judgements
    index = ctx.index
    packs = [_evidence_pack(ctx, index, c) for c in claims]
    judgements = await _judge(ctx, claims, packs)

    # 5-6. Verify quotes and apply verdict rules
    checks = [verify_claim(ctx, i, claim, judgements.get(i), content) for i, claim in enumerate(claims, start=1)]

    # 7-8. Citation integrity and source review (code only)
    issues: list[Issue] = []
    issues += claim_issues(checks, content)
    issues += citation_issues(ctx, content, checks)
    sources = source_assessments(ctx, content)

    # 9. Holistic review
    system, user = prompts.fact_review(lesson.request, content, lesson.sources)
    review = await reviewer.structured("fact_review", system=system, user=user, schema=FactReviewOut, temperature=0.0)
    for gap in review.gaps:
        section_id = content.sections[gap.section_index].id if gap.section_index is not None and 0 <= gap.section_index < len(content.sections) else None
        issues.append(Issue(
            id="", layer="facts", severity=gap.severity, category="accuracy", section_id=section_id,
            title=gap.title, detail=gap.detail, suggestion=gap.suggestion,
            fix=Fix(type="rewrite", instruction=gap.suggestion) if section_id else None,
        ))

    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: order[i.severity])
    for n, issue in enumerate(issues, start=1):
        issue.id = f"F{n}"

    report = FactReport(
        version=version, reviewer=reviewer.label, claims=checks, sources=sources, issues=issues,
        accuracy_score=accuracy(checks), summary=summarise(checks, sources),
    )
    lesson.fact_report = report
    return report.summary


def _evidence_pack(ctx: StepContext, index: PassageIndex, claim: ClaimOut) -> list[tuple[str, str, str]]:
    pack = []
    for passage, _ in index.search(claim.text, k=5, prefer_sources=claim.cited_source_ids):
        source = ctx.lesson.source(passage.source_id)
        if source:
            pack.append((passage.id, source_label(source), passage.text[:900]))
    return pack


async def _judge(ctx: StepContext, claims: list[ClaimOut], packs) -> dict[int, ClaimJudgementOut]:
    reviewer = ctx.require_reviewer()
    semaphore = asyncio.Semaphore(3)
    numbered = [(i, c.text, c.cited_source_ids, packs[i - 1]) for i, c in enumerate(claims, start=1)]
    batches = [numbered[i : i + BATCH] for i in range(0, len(numbered), BATCH)]

    async def one(batch):
        async with semaphore:
            system, user = prompts.judge_claims(batch)
            return await reviewer.structured("judge_claims", system=system, user=user, schema=ClaimJudgementsOut, temperature=0.0)

    results = await asyncio.gather(*(one(b) for b in batches))
    out: dict[int, ClaimJudgementOut] = {}
    for batch, result in zip(batches, results):
        numbers = [n for n, *_ in batch]
        valid = [j for j in result.judgements if j.claim_index in numbers]
        if len(valid) < len(result.judgements) and len(result.judgements) == len(batch):
            # The model renumbered the batch (for example from 1): match judgements by position instead.
            valid = [j.model_copy(update={"claim_index": n}) for j, n in zip(result.judgements, numbers)]
        for j in valid:
            out.setdefault(j.claim_index, j)
    return out


def verify_claim(ctx: StepContext, number: int, claim: ClaimOut, judgement: ClaimJudgementOut | None,
                 content: LessonContent) -> ClaimCheck:
    section = content.sections[claim.section_index]
    if judgement is None:
        return ClaimCheck(id=f"C{number}", section_id=section.id, text=claim.text, cited_source_ids=claim.cited_source_ids,
                          verdict="unsupported", evidence=[], note="The reviewer did not return a judgement for this claim.")
    evidence: list[Evidence] = []
    for item in judgement.evidence:
        source_id = item.source_id.split(".")[0].strip()  # accept passage ids such as S3.p2
        source = ctx.lesson.source(source_id)
        match, score = match_quote(item.quote, source.text or source.snippet) if source else ("not_found", 0.0)
        evidence.append(Evidence(source_id=source_id, quote=item.quote, match=match, match_score=score))
    verified = [e for e in evidence if e.match in ("exact", "close")]

    verdict, note, downgraded = judgement.verdict, judgement.note, False
    if verdict in ("supported", "partially_supported", "contradicted") and not verified:
        downgraded = True
        note = ("A contradiction was reported but its evidence could not be confirmed in the source."
                if verdict == "contradicted" else DOWNGRADE_NOTE)
        verdict = "unsupported"
    return ClaimCheck(
        id=f"C{number}", section_id=section.id, text=claim.text, cited_source_ids=claim.cited_source_ids,
        verdict=verdict, evidence=evidence, note=note, corrected_text=judgement.corrected_text, downgraded=downgraded,
    )


def claim_issues(checks: list[ClaimCheck], content: LessonContent) -> list[Issue]:
    issues = []
    for check in checks:
        if check.verdict == "supported":
            continue
        section = content.section(check.section_id)
        body = section.body_md if section else ""
        found = locate(check.text, body)
        fix = None
        if check.corrected_text and found:
            fix = Fix(type="replace", find=found, replace=check.corrected_text.strip().rstrip("."))
        else:
            fix = Fix(type="rewrite", instruction=(
                f"The statement \"{check.text}\" is {check.verdict.replace('_', ' ')} by the sources. "
                + (f"Correct it to: {check.corrected_text}. " if check.corrected_text else "")
                + "Rewrite it so it states only what the evidence supports, with a citation, or remove it."
            ))
        severity = {"contradicted": "high", "unsupported": "medium", "partially_supported": "low"}[check.verdict]
        title = {"contradicted": "Contradicted by a source", "unsupported": "Not supported by the sources",
                 "partially_supported": "Only partly supported"}[check.verdict]
        verified = [e for e in check.evidence if e.match in ("exact", "close")]
        detail = f"“{check.text}”"
        if check.note:
            detail += f" {check.note}"
        if verified:
            detail += f" Evidence [{verified[0].source_id}]: “{verified[0].quote}”"
        suggestion = (f"Change it to: {check.corrected_text}" if check.corrected_text
                      else "Support it with a source from the research, or remove it.")
        issues.append(Issue(id="", layer="facts", severity=severity, category=f"claim:{check.verdict}",
                            section_id=check.section_id, title=title, detail=detail, suggestion=suggestion, fix=fix))
    return issues


def citation_issues(ctx: StepContext, content: LessonContent, checks: list[ClaimCheck]) -> list[Issue]:
    issues: list[Issue] = []
    valid = {s.id: s for s in ctx.lesson.sources}
    for section in content.sections:
        ids = cited_ids(section.body_md)
        unknown = [i for i in ids if i not in valid]
        if unknown:
            issues.append(Issue(
                id="", layer="facts", severity="high", category="citation", section_id=section.id,
                title="Citation points to a source that does not exist",
                detail=f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not in the source list.",
                suggestion="Cite one of the listed sources or remove the citation.",
                fix=Fix(type="rewrite", instruction=f"Replace or remove the citations {', '.join(unknown)}; cite only real sources."),
            ))
        if section.kind in ("concept", "example") and not ids:
            issues.append(Issue(
                id="", layer="facts", severity="medium", category="citation", section_id=section.id,
                title="No citations in a section that states facts",
                detail=f"“{section.title}” makes factual statements without citing any source.",
                suggestion="Add citations to the sources that support each statement.",
                fix=Fix(type="rewrite", instruction="Add a citation to each factual statement, using only the evidence provided."),
            ))

    for check in checks:
        verified = [e for e in check.evidence if e.match in ("exact", "close")]
        if check.verdict != "supported" or not verified:
            continue
        support_ids = {e.source_id for e in verified}
        if all(valid[s].reliability.score < WEAK_SOURCE for s in support_ids if s in valid):
            issues.append(Issue(
                id="", layer="facts", severity="low", category="weak_source", section_id=check.section_id,
                title="Only supported by a low-reliability source",
                detail=f"“{check.text}” is supported only by {', '.join(sorted(support_ids))}.",
                suggestion="Find a primary or official source for this statement.",
            ))
        if check.cited_source_ids and not support_ids & set(check.cited_source_ids):
            best = sorted(support_ids)[0]
            issues.append(Issue(
                id="", layer="facts", severity="low", category="wrong_citation", section_id=check.section_id,
                title="Cited source does not contain this statement",
                detail=f"“{check.text}” cites {', '.join(check.cited_source_ids)}, but the supporting text is in {best}.",
                suggestion=f"Cite {best} instead.",
                fix=Fix(type="rewrite", instruction=f"For the statement \"{check.text}\", change its citation to [{best}]. Change nothing else."),
            ))
    return issues


def source_assessments(ctx: StepContext, content: LessonContent) -> list[SourceAssessment]:
    cited = set(lesson_cited_ids(content)) | {v.source_id for v in content.videos}
    terms = [t for a in (ctx.lesson.analysis.atoms if ctx.lesson.analysis else []) for t in a.key_terms]
    out = []
    for s in ctx.lesson.sources:
        flags = []
        if s.id not in cited:
            flags.append("Not cited")
        if s.kind == "book":
            flags.append("Bibliographic record only")
        if s.kind == "video" and not s.has_transcript:
            flags.append("No transcript to check")
        if s.reliability.score < WEAK_SOURCE:
            flags.append("Low reliability")
        if terms and s.text and relevance(s.text[:8000], terms) < 0.3:
            flags.append("Weak match to the topic")
        out.append(SourceAssessment(source_id=s.id, tier=s.reliability.tier, score=s.reliability.score, cited=s.id in cited, flags=flags))
    return out


def accuracy(checks: list[ClaimCheck]) -> float:
    if not checks:
        return 0.0
    supported = sum(1 for c in checks if c.verdict == "supported")
    partial = sum(1 for c in checks if c.verdict == "partially_supported")
    return round((supported + 0.5 * partial) / len(checks), 3)


def summarise(checks: list[ClaimCheck], sources: list[SourceAssessment]) -> str:
    if not checks:
        return "No checkable claims were found."
    counts = {v: sum(1 for c in checks if c.verdict == v) for v in ("supported", "partially_supported", "unsupported", "contradicted")}
    parts = [f"{counts['supported']} of {len(checks)} checkable claims are supported by the sources."]
    rest = []
    if counts["partially_supported"]:
        rest.append(f"{counts['partially_supported']} partly supported")
    if counts["unsupported"]:
        rest.append(f"{counts['unsupported']} unsupported")
    if counts["contradicted"]:
        rest.append(f"{counts['contradicted']} contradicted")
    if rest:
        parts.append(_join(rest).capitalize() + ".")
    uncited = sum(1 for s in sources if not s.cited)
    if uncited:
        parts.append(f"{uncited} of {len(sources)} sources are not cited.")
    return " ".join(parts)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
