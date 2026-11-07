"""Generation steps 1 to 5: analyse, plan research, research, outline, draft."""

from __future__ import annotations

import random
import re
import zlib

from ..models import (
    DraftOut,
    KnowledgeCheck,
    LessonContent,
    ObjectiveAnalysisOut,
    OutlineOut,
    OutlineSection,
    ResearchPlanOut,
    ResearchQuery,
    Section,
    Version,
    VideoPick,
)
from ..research.collector import Collector
from ..research.providers import ResearchError
from . import prompts
from .checks import CITATION, normalize_minutes
from .context import StepContext, StepError, evidence_for

REQUIRED_KINDS = ("hook", "concept", "example", "activity", "check", "recap")


# ---------------------------------------------------------------------------
# 1. Analyse the objective
# ---------------------------------------------------------------------------


async def analyze(ctx: StepContext) -> str:
    writer = ctx.require_writer()
    system, user = prompts.analyze(ctx.lesson.request)
    result = await writer.structured("analyze", system=system, user=user, schema=ObjectiveAnalysisOut, temperature=0.3)

    seen: set[str] = set()
    atoms = []
    for atom in result.atoms:
        key = " ".join(atom.statement.lower().split())
        if key in seen or not atom.verb.strip():
            continue
        seen.add(key)
        atoms.append(atom)
    for i, atom in enumerate(atoms, start=1):
        atom.id = f"O{i}"
    result.atoms = atoms
    ctx.lesson.analysis = result
    return f"{len(atoms)} objective parts: " + "; ".join(a.statement for a in atoms)


# ---------------------------------------------------------------------------
# 2. Plan research
# ---------------------------------------------------------------------------


async def plan_research(ctx: StepContext) -> str:
    writer = ctx.require_writer()
    analysis = _need_analysis(ctx)
    req = ctx.lesson.request
    system, user = prompts.plan_research(req, analysis)
    plan = await writer.structured("plan_research", system=system, user=user, schema=ResearchPlanOut, temperature=0.3)

    queries: list[ResearchQuery] = []
    seen: set[str] = set()
    for q in [ResearchQuery(query=req.title, purpose="Overview", atom_ids=[a.id for a in analysis.atoms]), *plan.web_queries]:
        key = q.query.lower().strip()
        if key and key not in seen:
            seen.add(key)
            queries.append(q)
    plan.web_queries = queries[:8]
    plan.video_queries = list(dict.fromkeys(v.strip() for v in plan.video_queries if v.strip()))[:3]
    plan.book_queries = list(dict.fromkeys(b.strip() for b in plan.book_queries if b.strip()))[:3]
    plan.authoritative_domains = [d.lower().strip().removeprefix("https://").removeprefix("http://").split("/")[0]
                                  for d in plan.authoritative_domains if d.strip()]
    ctx.lesson.research_plan = plan
    return (f"{len(plan.web_queries)} web, {len(plan.video_queries)} video and {len(plan.book_queries)} book queries; "
            f"authoritative: {', '.join(plan.authoritative_domains) or 'none named'}")


# ---------------------------------------------------------------------------
# 3. Research
# ---------------------------------------------------------------------------


async def research(ctx: StepContext) -> str:
    analysis = _need_analysis(ctx)
    plan = ctx.lesson.research_plan
    if plan is None:
        raise StepError("The research plan is missing. Retry from 'Plan the research'.")
    collector = Collector(ctx.toolkit, ctx.settings, ctx.log)
    try:
        sources = await collector.run(ctx.lesson.request, analysis, plan)
    except ResearchError as exc:
        ctx.lesson.research_log = collector.log
        raise StepError(str(exc)) from exc
    ctx.lesson.sources = sources
    ctx.lesson.research_log = collector.log
    ctx._index = None
    kinds = {k: sum(1 for s in sources if s.kind == k) for k in ("web", "instructor", "encyclopedia", "book", "video")}
    parts = [f"{kinds['web'] + kinds['instructor']} web", f"{kinds['encyclopedia']} encyclopedia",
             f"{kinds['book']} books", f"{kinds['video']} videos"]
    return f"{len(sources)} sources: " + ", ".join(parts)


# ---------------------------------------------------------------------------
# 4. Outline
# ---------------------------------------------------------------------------


def outline_problems(outline: OutlineOut, atom_ids: list[str]) -> list[str]:
    problems = []
    kinds = [s.kind for s in outline.sections]
    for kind in REQUIRED_KINDS:
        if kind not in kinds:
            problems.append(f"it has no {kind} section")
    if kinds.count("check") > 1:
        problems.append("it has more than one check section")
    if kinds and kinds[0] != "hook":
        problems.append("it does not start with the hook")
    if kinds and kinds[-1] != "recap":
        problems.append("it does not end with the recap")
    taught = {a for s in outline.sections if s.kind in ("concept", "example", "activity") for a in s.atom_ids}
    missing = [a for a in atom_ids if a not in taught]
    if missing:
        problems.append(f"objective parts {', '.join(missing)} are not taught in any concept, example or activity section")
    return problems


def repair_order(outline: OutlineOut) -> OutlineOut:
    """Move the hook to the front and the recap to the end when the model only got the order wrong."""
    sections = outline.sections
    hooks = [s for s in sections if s.kind == "hook"][:1]
    recaps = [s for s in sections if s.kind == "recap"][-1:]
    middle = [s for s in sections if s not in hooks and s not in recaps]
    return OutlineOut(sections=hooks + middle + recaps)


async def outline(ctx: StepContext) -> str:
    writer = ctx.require_writer()
    analysis = _need_analysis(ctx)
    req = ctx.lesson.request
    atom_ids = [a.id for a in analysis.atoms]
    minutes = ctx.settings.lesson_minutes

    problem = None
    result: OutlineOut | None = None
    for attempt in range(2):
        system, user = prompts.outline(req, analysis, ctx.lesson.sources, minutes, problem)
        result = repair_order(await writer.structured("outline", system=system, user=user, schema=OutlineOut, temperature=0.3))
        problems = outline_problems(result, atom_ids)
        # Missing objective coverage is reported by QC Layer 2 rather than failing the step.
        blocking = [p for p in problems if "objective parts" not in p]
        if not blocking:
            break
        problem = "; ".join(problems)
        await ctx.log(f"The lesson plan needs another pass: {problem}.", "warn")
    else:
        raise StepError(f"The lesson plan was incomplete twice ({problem}). Retry this step.")

    assert result is not None
    check = next(s for s in result.sections if s.kind == "check")
    check.atom_ids = atom_ids  # the check section always covers the whole objective
    for section in result.sections:
        section.atom_ids = [a for a in dict.fromkeys(section.atom_ids) if a in atom_ids]
    scaled = normalize_minutes([s.minutes for s in result.sections], minutes)
    for section, m in zip(result.sections, scaled):
        section.minutes = m
    ctx.lesson.outline = result
    return " | ".join(f"{s.title} {s.minutes}m" for s in result.sections)


# ---------------------------------------------------------------------------
# 5. Draft
# ---------------------------------------------------------------------------


def clean_citations(markdown: str, valid: set[str]) -> tuple[str, int]:
    """Remove citation ids that do not match a real source. Returns (text, number removed)."""
    removed = 0

    def fix(match: re.Match) -> str:
        nonlocal removed
        ids = [p.strip() for p in re.split(r"[,;]", match.group(1))]
        kept = [i for i in ids if i in valid]
        removed += len(ids) - len(kept)
        return f"[{', '.join(kept)}]" if kept else ""

    return CITATION.sub(fix, markdown), removed


def shuffle_options(options: list[str], answer_index: int, seed_text: str) -> tuple[list[str], int]:
    """Shuffle answer options with a stable seed so the correct answer is not always in the same place."""
    order = list(range(len(options)))
    random.Random(zlib.crc32(seed_text.encode())).shuffle(order)
    return [options[i] for i in order], order.index(answer_index)


async def draft(ctx: StepContext) -> str:
    writer = ctx.require_writer()
    analysis = _need_analysis(ctx)
    outline_ = ctx.lesson.outline
    if outline_ is None:
        raise StepError("The lesson plan is missing. Retry from 'Plan 45 minutes'.")
    req = ctx.lesson.request
    atom_terms = {a.id: " ".join(a.key_terms) for a in analysis.atoms}

    evidence: dict[int, list[tuple[str, str, str]]] = {}
    for i, section in enumerate(outline_.sections):
        if section.kind in ("check",):
            continue
        query = " ".join([section.title, section.plan, *(atom_terms.get(a, "") for a in section.atom_ids)])
        evidence[i] = evidence_for(ctx, query, k=5)
    videos = [s for s in ctx.lesson.sources if s.kind == "video"]

    system, user = prompts.draft(req, analysis, outline_.sections, evidence, videos, ctx.settings.reading_words_per_minute)
    result = await writer.structured("draft", system=system, user=user, schema=DraftOut, temperature=0.5, max_tokens=32000)

    content, notes = assemble(result, outline_.sections, ctx)
    for note in notes:
        await ctx.log(note, "warn")
    reason = "Generated" if not ctx.lesson.versions else "Regenerated"
    ctx.lesson.versions.append(Version(number=ctx.lesson.version_number + 1, reason=reason, content=content))
    return f"Version {ctx.lesson.version_number}: {len(content.sections)} sections, {len(content.knowledge_checks)} questions, {content.total_minutes} minutes"


def assemble(result: DraftOut, plan: list[OutlineSection], ctx: StepContext) -> tuple[LessonContent, list[str]]:
    notes: list[str] = []
    valid = {s.id for s in ctx.lesson.sources}
    by_index = {d.index: d for d in result.sections}
    if any(i not in by_index for i in range(len(plan))) and len(result.sections) == len(plan):
        by_index = dict(enumerate(result.sections))  # numbered from 1 or renumbered: trust the order
    missing = [i for i in range(len(plan)) if i not in by_index]
    if missing:
        raise StepError(f"The draft skipped {len(missing)} of the planned sections. Retry this step.")

    sections: list[Section] = []
    removed_total = 0
    for i, planned in enumerate(plan):
        body, removed = clean_citations(by_index[i].body_md.strip(), valid)
        removed_total += removed
        sections.append(
            Section(id=f"sec-{i + 1}", kind=planned.kind, title=planned.title, minutes=planned.minutes,
                    atom_ids=planned.atom_ids, body_md=_strip_leading_title(body, planned.title),
                    instructor_notes=by_index[i].instructor_notes.strip())
        )
    if removed_total:
        notes.append(f"Removed {removed_total} citation(s) to sources that do not exist.")

    atom_ids = {a.id for a in _need_analysis(ctx).atoms}
    checks: list[KnowledgeCheck] = []
    for n, k in enumerate(result.knowledge_checks, start=1):
        options, answer = shuffle_options(k.options, k.answer_index, k.question)
        checks.append(
            KnowledgeCheck(id=f"kc-{n}", atom_ids=[a for a in k.atom_ids if a in atom_ids] or k.atom_ids,
                           question=k.question.strip(), options=[o.strip() for o in options], answer_index=answer,
                           explanation=k.explanation.strip(), source_ids=[s for s in k.source_ids if s in valid])
        )
    video_ids = {s.id for s in ctx.lesson.sources if s.kind == "video"}
    videos = [VideoPick(source_id=v.source_id, why=v.why) for v in result.videos if v.source_id in video_ids]
    if len(videos) < len(result.videos):
        notes.append("Dropped video picks that did not match a video source.")
    return LessonContent(summary=result.summary.strip(), sections=sections, knowledge_checks=checks, videos=videos), notes


def _strip_leading_title(body: str, title: str) -> str:
    lines = body.splitlines()
    if lines and lines[0].lstrip("#").strip().lower() == title.strip().lower():
        return "\n".join(lines[1:]).strip()
    return body


def _need_analysis(ctx: StepContext) -> ObjectiveAnalysisOut:
    if ctx.lesson.analysis is None:
        raise StepError("The objective breakdown is missing. Retry from 'Break down the objective'.")
    return ctx.lesson.analysis
