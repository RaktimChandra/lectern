"""Preview and apply QC fixes, and every other change that creates a version.

Nothing changes the lesson without a new version: edits, applied fixes and
restores all append a version with a reason, so any earlier state can be
inspected or restored.
"""

from __future__ import annotations

from ..models import (
    Issue,
    KnowledgeCheck,
    KnowledgeCheckOut,
    Lesson,
    LessonContent,
    RewriteOut,
    Version,
)
from . import prompts
from .checks import normalize_minutes
from .context import StepContext, StepError, evidence_for
from .steps import clean_citations, shuffle_options


class Conflict(Exception):
    """The lesson changed since the client loaded it."""


def require_version(lesson: Lesson, base_version: int) -> None:
    if base_version != lesson.version_number:
        raise Conflict(
            f"This lesson changed since you opened it (you have version {base_version}, the latest is "
            f"{lesson.version_number}). Reload to see the latest version."
        )


def new_version(lesson: Lesson, content: LessonContent, reason: str) -> Version:
    version = Version(number=lesson.version_number + 1, reason=reason, content=content)
    lesson.versions.append(version)
    return version


def current_content(lesson: Lesson) -> LessonContent:
    if lesson.current is None:
        raise StepError("This lesson has no content yet.")
    return lesson.current.content.model_copy(deep=True)


# ---------------------------------------------------------------------------
# Direct edits
# ---------------------------------------------------------------------------


def edit_section(lesson: Lesson, section_id: str, *, body_md: str, title: str | None, minutes: int | None,
                 instructor_notes: str | None, total_minutes: int) -> Version:
    content = current_content(lesson)
    section = content.section(section_id)
    if section is None:
        raise KeyError(section_id)
    # Instructor text is saved exactly as typed; QC Layer 1 flags any citation that points nowhere.
    section.body_md = body_md.strip()
    if title is not None and title.strip():
        section.title = title.strip()
    if instructor_notes is not None:
        section.instructor_notes = instructor_notes.strip()
    if minutes is not None and minutes != section.minutes:
        rebalance(content, section_id, minutes, total_minutes)
    return new_version(lesson, content, f"Edited: {section.title}")


def rebalance(content: LessonContent, section_id: str, minutes: int, total: int) -> None:
    """Give one section a new length and scale the others so the lesson still adds up to `total`."""
    others = [s for s in content.sections if s.id != section_id]
    minimum = 2
    minutes = max(minimum, min(minutes, total - minimum * len(others)))
    scaled = normalize_minutes([s.minutes for s in others], total - minutes, minimum)
    for s, m in zip(others, scaled):
        s.minutes = m
    content.section(section_id).minutes = minutes  # type: ignore[union-attr]


def edit_check(lesson: Lesson, check_id: str, *, question: str, options: list[str], answer_index: int,
               explanation: str) -> Version:
    content = current_content(lesson)
    check = next((k for k in content.knowledge_checks if k.id == check_id), None)
    if check is None:
        raise KeyError(check_id)
    if not 0 <= answer_index < len(options) or not options[answer_index].strip():
        raise ValueError("Mark one of the filled-in options as the correct answer.")
    kept = [o.strip() for o in options if o.strip()]
    if len(kept) < 2 or not question.strip():
        raise ValueError("A question needs text and at least two options.")
    # Blank options are dropped, so find the correct answer's new position by identity, not by index.
    new_index = [i for i, o in enumerate(options) if o.strip()].index(answer_index)
    check.question, check.options, check.answer_index, check.explanation = question.strip(), kept, new_index, explanation.strip()
    return new_version(lesson, content, f"Edited question {check_id}")


def restore(lesson: Lesson, number: int) -> Version:
    old = next((v for v in lesson.versions if v.number == number), None)
    if old is None:
        raise KeyError(number)
    return new_version(lesson, old.content.model_copy(deep=True), f"Restored version {number}")


# ---------------------------------------------------------------------------
# QC fixes
# ---------------------------------------------------------------------------


def render_check(check: KnowledgeCheck | KnowledgeCheckOut) -> str:
    lines = [f"**{check.question}**", ""]
    for i, option in enumerate(check.options):
        mark = " (correct)" if i == check.answer_index else ""
        lines.append(f"{chr(65 + i)}. {option}{mark}")
    lines += ["", check.explanation]
    return "\n".join(lines)


async def preview(ctx: StepContext, issue: Issue) -> dict:
    lesson = ctx.lesson
    content = current_content(lesson)
    fix = issue.fix
    if fix is None:
        raise StepError("This finding has no automatic fix. Edit the lesson directly, or dismiss it.")

    if fix.type == "add_check":
        atom_id = issue.atom_id or fix.instruction or ""
        atom = next((a for a in (lesson.analysis.atoms if lesson.analysis else []) if a.id == atom_id), None)
        if atom is None:
            raise StepError(f"Objective part {atom_id} no longer exists.")
        writer = ctx.require_writer()
        evidence = evidence_for(ctx, " ".join([atom.statement, *atom.key_terms]), k=4)
        system, user = prompts.add_check(lesson.request, atom.statement, atom.id, content, evidence)
        new = await writer.structured("add_check", system=system, user=user, schema=KnowledgeCheckOut, temperature=0.4)
        new.atom_ids = [atom.id]
        return {"kind": "check", "section_id": issue.section_id, "before": "", "after": render_check(new),
                "method": "rewrite", "change_summary": f"Adds a question that tests {atom.id}.", "check": new.model_dump()}

    section = content.section(issue.section_id or "")
    if section is None:
        raise StepError("The section this finding refers to no longer exists.")

    if fix.type == "replace" and fix.find and fix.find in section.body_md:
        after = section.body_md.replace(fix.find, fix.replace or "", 1)
        return {"kind": "section", "section_id": section.id, "before": section.body_md, "after": after,
                "method": "exact", "change_summary": "Replaces the flagged text.", "check": None}

    writer = ctx.require_writer()
    query = " ".join([issue.detail, issue.suggestion, section.title])
    evidence = evidence_for(ctx, query, k=5)
    system, user = prompts.rewrite_section(section, f"{issue.title}. {issue.detail}", issue.suggestion, fix.instruction, evidence)
    result = await writer.structured("rewrite_section", system=system, user=user, schema=RewriteOut, temperature=0.3)
    after, _ = clean_citations(result.body_md.strip(), {s.id for s in lesson.sources})
    return {"kind": "section", "section_id": section.id, "before": section.body_md, "after": after,
            "method": "rewrite", "change_summary": result.change_summary, "check": None}


def apply(lesson: Lesson, issue: Issue, *, after: str | None, check: dict | None) -> Version:
    if issue.status != "open":
        raise StepError(f"{issue.id} has already been {issue.status}.")
    is_check = issue.fix is not None and issue.fix.type == "add_check"
    if is_check != (check is not None):
        raise StepError("This fix does not match the finding. Preview it again and apply the preview.")
    content = current_content(lesson)
    if check is not None:
        new = KnowledgeCheckOut.model_validate(check)
        options, answer = shuffle_options(new.options, new.answer_index, new.question)
        number = max((int(k.id.split("-")[1]) for k in content.knowledge_checks), default=0) + 1
        valid = {s.id for s in lesson.sources}
        content.knowledge_checks.append(KnowledgeCheck(
            id=f"kc-{number}", atom_ids=new.atom_ids, question=new.question, options=options, answer_index=answer,
            explanation=new.explanation, source_ids=[s for s in new.source_ids if s in valid]))
    else:
        section = content.section(issue.section_id or "")
        if section is None or after is None:
            raise StepError("Nothing to apply: preview the fix first.")
        section.body_md = after.strip()
    version = new_version(lesson, content, f"Applied {issue.id}: {issue.title}")
    issue.status, issue.resolved_in_version = "applied", version.number
    return version


def apply_all_exact(lesson: Lesson) -> tuple[Version | None, list[str]]:
    content = current_content(lesson)
    applied: list[Issue] = []
    for issue in lesson.all_issues():
        fix = issue.fix
        if issue.status != "open" or fix is None or fix.type != "replace" or not fix.find:
            continue
        section = content.section(issue.section_id or "")
        if section and fix.find in section.body_md:
            section.body_md = section.body_md.replace(fix.find, fix.replace or "", 1)
            applied.append(issue)
    if not applied:
        return None, []
    version = new_version(lesson, content, f"Applied {len(applied)} exact fixes: {', '.join(i.id for i in applied)}")
    for issue in applied:
        issue.status, issue.resolved_in_version = "applied", version.number
    return version, [i.id for i in applied]


def dismiss(issue: Issue, reason: str | None) -> Issue:
    issue.status = "dismissed"
    issue.dismiss_reason = (reason or "").strip() or None
    return issue
