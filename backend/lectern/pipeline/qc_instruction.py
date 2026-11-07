"""QC Layer 2: instructional quality.

Coverage, timing, structure and readability are measured in code. The
reviewer model scores a six-criterion rubric and lists teaching issues; it is
given the measured findings so it does not repeat them. This layer never sees
QC Layer 1's output.
"""

from __future__ import annotations

import re

from ..models import Fix, InstructionReport, InstructionReviewOut, Issue, LessonContent
from . import prompts
from .checks import (
    CODE_FENCE,
    coverage,
    lesson_cited_ids,
    readability,
    readability_band,
    section_timing,
)
from .context import StepContext, StepError
from .qc_facts import locate

NUMBERED_STEP = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)


def deterministic_issues(ctx: StepContext, content: LessonContent, minutes: int):
    analysis = ctx.lesson.analysis
    atoms = analysis.atoms if analysis else []
    wpm = ctx.settings.reading_words_per_minute
    rows = coverage(content, atoms)
    timing = [section_timing(s, wpm) for s in content.sections]
    issues: list[Issue] = []

    def add(severity, category, title, detail, suggestion, section_id=None, fix=None, atom_id=None):
        issues.append(Issue(id="", layer="instruction", severity=severity, category=category, section_id=section_id,
                            title=title, detail=detail, suggestion=suggestion, fix=fix, atom_id=atom_id))

    total = content.total_minutes
    if total != minutes:
        add("high", "pacing", f"The lesson adds up to {total} minutes, not {minutes}",
            "Section minutes must total the lesson length.", f"Adjust section minutes so they add up to {minutes}.")

    check_section = next((s for s in content.sections if s.kind == "check"), None)
    for row in rows:
        if row.status == "missing":
            add("high", "alignment", f"{row.atom_id} is not taught or tested",
                f"Nothing in the lesson teaches or tests: {row.statement}",
                "Add explanation and practice for this part, then a question that tests it.", atom_id=row.atom_id)
        elif row.status == "taught_not_assessed":
            add("medium", "assessment", f"{row.atom_id} is taught but not tested",
                f"No knowledge check tests: {row.statement}", "Add a question for this part.",
                section_id=check_section.id if check_section else None,
                fix=Fix(type="add_check", instruction=row.atom_id), atom_id=row.atom_id)
        elif row.status == "assessed_not_taught":
            add("medium", "alignment", f"{row.atom_id} is tested but not taught",
                f"A question tests “{row.statement}” but no concept, example or activity section is tagged with it.",
                "Teach this part before testing it, or tag the section that already covers it.", atom_id=row.atom_id)

    for t in timing:
        section = content.section(t.section_id)
        if not section or t.status == "ok":
            continue
        if t.status == "too_long":
            target = round(section.minutes * ctx.settings.reading_words_per_minute * (0.5 if section.kind in ("activity", "check") else 1.0))
            add("medium", "pacing", f"“{section.title}” does not fit its {section.minutes} minutes",
                f"About {t.estimated_minutes} minutes to read ({t.words} words) against {section.minutes} allotted.",
                f"Cut it to about {target} words, or give it more minutes.", section_id=section.id,
                fix=Fix(type="rewrite", instruction=f"Shorten this section to about {target} words, keeping every key idea and citation."))
        else:
            target = round(section.minutes * ctx.settings.reading_words_per_minute * 0.6)
            add("low", "pacing", f"“{section.title}” is thin for {section.minutes} minutes",
                f"About {t.estimated_minutes} minutes of reading against {section.minutes} allotted.",
                f"Add a worked example or a short exercise, up to about {target} words, or give the time to another section.",
                section_id=section.id,
                fix=Fix(type="rewrite", instruction=f"Expand this section to about {target} words with a concrete example, using only the evidence provided."))

    kinds = [s.kind for s in content.sections]
    for kind, label in (("example", "a worked example"), ("activity", "an activity"), ("recap", "a recap")):
        if kind not in kinds:
            add("high", "structure", f"The lesson has no {kind} section", f"A 45-minute lesson needs {label}.",
                f"Add {label}.")
    if len(content.knowledge_checks) < 2:
        add("high", "assessment", "Too few knowledge checks", "The lesson has fewer than two questions.",
            "Add questions so every objective part is tested.")

    for section in content.sections:
        if section.kind == "activity":
            has_steps = len(NUMBERED_STEP.findall(section.body_md)) >= 2
            has_check = bool(re.search(r"expect|should see|check your|answer|solution|result", section.body_md, re.IGNORECASE))
            if not (has_steps and has_check):
                missing = [m for m, ok in (("numbered steps", has_steps), ("a way to check the result", has_check)) if not ok]
                add("medium", "practice", "The activity is hard to do alone",
                    f"“{section.title}” is missing {' and '.join(missing)}.",
                    "Give numbered steps and an expected result the learner can compare against.", section_id=section.id,
                    fix=Fix(type="rewrite", instruction="Restructure the activity into numbered steps and add the expected result so a learner can check their work."))
        stats = readability(section.body_md)
        if section.kind in ("concept", "example") and stats["flesch_reading_ease"] is not None and (
            stats["flesch_reading_ease"] < 30 or stats["long_sentences"] >= 3
        ):
            add("low", "clarity", f"“{section.title}” is dense",
                f"Reading ease {stats['flesch_reading_ease']} ({readability_band(stats['flesch_reading_ease'])}), "
                f"{stats['long_sentences']} sentences over 30 words.",
                "Split long sentences and define terms as they appear.", section_id=section.id,
                fix=Fix(type="rewrite", instruction="Split sentences longer than 25 words and define each technical term on first use. Keep all citations."))
        for block in CODE_FENCE.findall(section.body_md):
            if block.startswith("```\n") or block.startswith("```\r\n"):
                add("low", "accessibility", "Code block without a language", f"A code block in “{section.title}” has no language tag.",
                    "Add a language tag (for example ```http or ```bash) so it is highlighted correctly.", section_id=section.id)
                break

    for k in content.knowledge_checks:
        if len(k.explanation.split()) < 12:
            add("low", "assessment", f"Thin explanation for question {k.id}", f"“{k.question}” explains its answer in under 12 words.",
                "Say why the answer is right and why the most tempting wrong option is wrong.")
        if len({o.strip().lower() for o in k.options}) < len(k.options):
            add("medium", "assessment", f"Duplicate options in question {k.id}", f"“{k.question}” repeats an option.",
                "Make every option distinct.")

    if any(s.kind == "video" for s in ctx.lesson.sources) and not content.videos:
        add("low", "engagement", "No videos recommended", "Video sources were found but none is recommended.",
            "Recommend one or two videos with the segment worth watching.")
    if len(lesson_cited_ids(content)) < 3:
        add("medium", "alignment", "Few sources cited", "Fewer than three distinct sources are cited.",
            "Ground the lesson in more of the research.")

    return rows, timing, issues


def automated_summary(rows, timing, stats, content: LessonContent) -> str:
    cov = "; ".join(f"{r.atom_id}: {r.status.replace('_', ' ')}" for r in rows) or "no objective parts"
    tim = "; ".join(f"{content.section(t.section_id).title if content.section(t.section_id) else t.section_id}: "
                    f"{t.allotted_minutes} min allotted, about {t.estimated_minutes} to read ({t.status.replace('_', ' ')})"
                    for t in timing)
    return (f"- Coverage: {cov}\n- Timing: {tim}\n- Readability: Flesch {stats['flesch_reading_ease']} "
            f"({readability_band(stats['flesch_reading_ease'])}), average sentence {stats['avg_sentence_words']} words")


async def run(ctx: StepContext) -> str:
    lesson = ctx.lesson
    if lesson.current is None:
        raise StepError("There is no lesson to review yet. Retry from 'Write the lesson'.")
    reviewer = ctx.require_reviewer()
    content = lesson.current.content
    minutes = ctx.settings.lesson_minutes

    rows, timing, issues = deterministic_issues(ctx, content, minutes)
    all_text = "\n\n".join(s.body_md for s in content.sections)
    stats = readability(all_text)

    system, user = prompts.instruction_review(lesson.request, lesson.analysis, content, automated_summary(rows, timing, stats, content))
    review = await reviewer.structured("instruction_review", system=system, user=user, schema=InstructionReviewOut, temperature=0.0)

    for item in review.issues:
        section = content.sections[item.section_index] if item.section_index is not None and 0 <= item.section_index < len(content.sections) else None
        fix = None
        if section is not None:
            found = locate(item.find, section.body_md) if item.find and item.replace is not None else None
            if found and section.body_md.count(found) == 1:
                fix = Fix(type="replace", find=found, replace=item.replace)
            else:
                fix = Fix(type="rewrite", instruction=item.suggestion)
        issues.append(Issue(id="", layer="instruction", severity=item.severity, category=item.category,
                            section_id=section.id if section else None, title=item.title, detail=item.detail,
                            suggestion=item.suggestion, fix=fix))

    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: order[i.severity])
    for n, issue in enumerate(issues, start=1):
        issue.id = f"I{n}"

    rubric_mean = sum(r.score for r in review.rubric) / len(review.rubric)
    covered = sum(1 for r in rows if r.status == "covered") / len(rows) if rows else 0.0
    timing_ok = sum(1 for t in timing if t.status == "ok") / len(timing) if timing else 0.0
    quality = round(70 * rubric_mean / 5 + 20 * covered + 10 * timing_ok, 1)

    high = sum(1 for i in issues if i.severity == "high")
    summary = (
        f"{sum(1 for r in rows if r.status == 'covered')} of {len(rows)} objective parts are taught and tested. "
        f"Timing fits in {sum(1 for t in timing if t.status == 'ok')} of {len(timing)} sections. "
        f"Rubric average {rubric_mean:.1f} of 5. {len(issues)} suggestion{'s' if len(issues) != 1 else ''}"
        + (f", {high} high priority." if high else ".")
    )
    lesson.instruction_report = InstructionReport(
        version=lesson.version_number, reviewer=reviewer.label, coverage=rows, timing=timing,
        total_minutes=content.total_minutes, estimated_total_minutes=round(sum(t.estimated_minutes for t in timing), 1),
        readability=stats, rubric=review.rubric, strengths=review.strengths, issues=issues,
        quality_score=quality, summary=summary,
    )
    return summary
