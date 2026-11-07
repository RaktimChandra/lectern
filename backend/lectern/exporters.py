"""Exports: Markdown, standalone HTML, JSON and a ZIP bundle with both QC reports.

References are built here from the sources the lesson actually cites, in the
order they are first cited. Only metadata the providers returned is printed;
nothing is guessed.
"""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from datetime import datetime

from markdown_it import MarkdownIt

from .models import FactReport, InstructionReport, Lesson, LessonContent, Source
from .pipeline.checks import CITATION, lesson_cited_ids

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "lesson"


def mmss(seconds: int | None) -> str:
    if seconds is None:
        return ""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def cited_sources(lesson: Lesson, content: LessonContent) -> list[Source]:
    ids = lesson_cited_ids(content) + [v.source_id for v in content.videos]
    seen, out = set(), []
    for sid in ids:
        source = lesson.source(sid)
        if source and sid not in seen:
            seen.add(sid)
            out.append(source)
    return sorted(out, key=lambda s: int(s.id[1:]) if s.id[1:].isdigit() else 0)


def reference_text(source: Source) -> str:
    retrieved = source.retrieved_at.strftime("%d %b %Y").lstrip("0")
    if source.kind == "book":
        parts = []
        if source.authors:
            parts.append(", ".join(source.authors) + ".")
        if source.year:
            parts.append(f"({source.year}).")
        parts.append(f"{source.title}.")
        if source.publisher:
            parts.append(f"{source.publisher}.")
        if source.isbn:
            parts.append(f"ISBN {source.isbn}.")
        parts.append(f"{source.url} (book record)")
        return " ".join(parts)
    if source.kind == "video":
        meta = ", ".join(p for p in (source.channel, str(source.year) if source.year else "", mmss(source.duration_seconds)) if p)
        text = f"Video: “{source.title}” ({meta})."
        if source.best_segment:
            text += f" Most relevant part: {mmss(source.best_segment.start_seconds)} to {mmss(source.best_segment.end_seconds)}."
        return f"{text} {source.url}"
    if source.kind == "encyclopedia":
        return f"{source.title}. {source.url} (retrieved {retrieved})"
    site = source.publisher or source.domain
    return f"{site}. {source.title}. {source.url} (retrieved {retrieved})"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def lesson_markdown(lesson: Lesson) -> str:
    version = lesson.current
    if version is None:
        raise ValueError("This lesson has no content yet.")
    content, req = version.content, lesson.request
    out = [
        "---",
        f"title: {json.dumps(req.title)}",
        f"objective: {json.dumps(req.objective)}",
        f"duration_minutes: {content.total_minutes}",
        f"audience: {req.audience}",
        f"delivery: {req.mode.replace('_', '-')}",
        f"version: {version.number}",
        f"generated: {version.created_at.date().isoformat()}",
        "---",
        "",
        f"# {req.title}",
        "",
        content.summary,
        "",
        f"**Learning objective:** {req.objective}",
        "",
    ]
    if lesson.analysis:
        out.append("**By the end of this lesson you will be able to:**")
        out += [f"- {a.statement}" for a in lesson.analysis.atoms]
        out.append("")
    out += ["| Part | Section | Minutes |", "|---|---|---|"]
    out += [f"| {i} | {s.title} | {s.minutes} |" for i, s in enumerate(content.sections, start=1)]
    out += [f"| | **Total** | **{content.total_minutes}** |", ""]

    answer_key = []
    q = 0
    for i, section in enumerate(content.sections, start=1):
        out += [f"## {i}. {section.title} ({section.minutes} min)", "", section.body_md.strip(), ""]
        if section.kind == "check":
            for check in content.knowledge_checks:
                q += 1
                out.append(f"**Question {q}.** {check.question}")
                out.append("")
                out += [f"- {chr(65 + n)}. {opt}" for n, opt in enumerate(check.options)]
                out.append("")
                answer_key.append(f"{q}. **{chr(65 + check.answer_index)}**. {check.explanation}")
        if section.instructor_notes:
            out += [f"> **Instructor notes:** {section.instructor_notes}", ""]

    if content.videos:
        out += ["## Watch next", "", "Optional, outside the 45 minutes.", ""]
        for pick in content.videos:
            source = lesson.source(pick.source_id)
            if not source:
                continue
            segment = (f" Watch {mmss(source.best_segment.start_seconds)} to {mmss(source.best_segment.end_seconds)}."
                       if source.best_segment else "")
            out.append(f"- [{source.title}]({source.url}) ({source.channel or 'YouTube'}, {mmss(source.duration_seconds)}).{segment} {pick.why} [{source.id}]")
        out.append("")

    if answer_key:
        out += ["## Answer key", ""] + answer_key + [""]
    out += ["## References", ""]
    out += [f"[{s.id}] {reference_text(s)}  " for s in cited_sources(lesson, content)]
    out.append("")
    return "\n".join(out)


def references_markdown(lesson: Lesson) -> str:
    content = lesson.current.content if lesson.current else None
    lines = [f"# References: {lesson.request.title}", ""]
    if content:
        lines += [f"[{s.id}] {reference_text(s)}" for s in cited_sources(lesson, content)]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML_STYLE = """
:root { --ink:#1C2533; --muted:#5B6878; --rule:#D5DCE3; --marker:#F2D24B; }
* { box-sizing: border-box; }
body { margin:0; background:#EEF1F4; color:var(--ink); font:18px/1.65 Georgia, 'Source Serif 4', serif; }
main { max-width: 760px; margin: 40px auto; background:#fff; padding: 56px 64px; box-shadow: 0 1px 2px rgba(28,37,51,.12); }
h1 { font-size: 34px; line-height: 1.2; margin: 0 0 16px; }
h2 { font-size: 24px; margin: 48px 0 8px; padding-top: 12px; border-top: 1px solid var(--rule); }
.meta, .min { font: 14px/1.5 system-ui, sans-serif; color: var(--muted); }
.objective { border-left: 4px solid var(--marker); padding: 4px 0 4px 16px; margin: 24px 0; }
table { border-collapse: collapse; width: 100%; font: 15px/1.4 system-ui, sans-serif; }
td, th { border: 1px solid var(--rule); padding: 6px 10px; text-align: left; }
pre { background: #F4F6F8; padding: 14px 16px; overflow-x: auto; font: 14px/1.5 ui-monospace, Consolas, monospace; }
code { font-family: ui-monospace, Consolas, monospace; font-size: .88em; }
sup a { text-decoration: none; font: 12px system-ui, sans-serif; color: #2B59C3; }
.q { margin: 20px 0; } .q ol { list-style: upper-alpha; }
details { font: 15px/1.5 system-ui, sans-serif; color: var(--muted); }
.notes { font: 15px/1.5 system-ui, sans-serif; background: #F7F8FA; padding: 10px 14px; border-left: 3px solid var(--rule); }
.refs li { font-size: 15px; margin-bottom: 6px; word-break: break-word; }
@media print { body { background: #fff; } main { box-shadow: none; margin: 0; padding: 0; } details { display: block; }
  details > summary { display: none; } h2 { break-after: avoid; } pre, .q { break-inside: avoid; } }
"""


def _render(markdown: str, ref_ids: set[str]) -> str:
    rendered = _md.render(markdown)

    def link(match: re.Match) -> str:
        ids = [p.strip() for p in re.split(r"[,;]", match.group(1))]
        return "".join(f'<sup><a href="#ref-{i}">[{i}]</a></sup>' if i in ref_ids else f"<sup>[{i}]</sup>" for i in ids)

    return CITATION.sub(link, rendered)


def lesson_html(lesson: Lesson) -> str:
    version = lesson.current
    if version is None:
        raise ValueError("This lesson has no content yet.")
    content, req = version.content, lesson.request
    refs = cited_sources(lesson, content)
    ref_ids = {s.id for s in refs}
    e = html.escape
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{e(req.title)}</title><style>{HTML_STYLE}</style></head><body><main>",
        f"<h1>{e(req.title)}</h1>",
        f"<p class='meta'>{content.total_minutes} minutes. {e(req.audience.capitalize())}. "
        f"{'Self-paced' if req.mode == 'self_paced' else 'Instructor-led'}. Version {version.number}, "
        f"{version.created_at.strftime('%d %B %Y').lstrip('0')}.</p>",
        f"<p>{e(content.summary)}</p>",
        f"<div class='objective'><strong>Learning objective.</strong> {e(req.objective)}",
    ]
    if lesson.analysis:
        parts.append("<ul>" + "".join(f"<li>{e(a.statement)}</li>" for a in lesson.analysis.atoms) + "</ul>")
    parts.append("</div>")
    parts.append("<table><thead><tr><th>Part</th><th>Section</th><th>Minutes</th></tr></thead><tbody>")
    parts += [f"<tr><td>{i}</td><td>{e(s.title)}</td><td>{s.minutes}</td></tr>" for i, s in enumerate(content.sections, 1)]
    parts.append(f"<tr><td></td><th>Total</th><th>{content.total_minutes}</th></tr></tbody></table>")

    q = 0
    for i, section in enumerate(content.sections, start=1):
        parts.append(f"<h2 id='{e(section.id)}'>{i}. {e(section.title)} <span class='min'>{section.minutes} min</span></h2>")
        parts.append(_render(section.body_md, ref_ids))
        if section.kind == "check":
            for check in content.knowledge_checks:
                q += 1
                options = "".join(f"<li>{e(o)}</li>" for o in check.options)
                parts.append(
                    f"<div class='q'><p><strong>Question {q}.</strong> {e(check.question)}</p><ol>{options}</ol>"
                    f"<details><summary>Show answer</summary><p><strong>{chr(65 + check.answer_index)}.</strong> "
                    f"{e(check.explanation)}</p></details></div>"
                )
        if section.instructor_notes:
            parts.append(f"<p class='notes'><strong>Instructor notes.</strong> {e(section.instructor_notes)}</p>")

    if content.videos:
        parts.append("<h2>Watch next</h2><p class='meta'>Optional, outside the 45 minutes.</p><ul>")
        for pick in content.videos:
            s = lesson.source(pick.source_id)
            if not s:
                continue
            seg = (f" Watch {mmss(s.best_segment.start_seconds)} to {mmss(s.best_segment.end_seconds)}." if s.best_segment else "")
            parts.append(f"<li><a href='{e(s.url)}'>{e(s.title)}</a> ({e(s.channel or 'YouTube')}, {mmss(s.duration_seconds)}).{seg} {e(pick.why)}</li>")
        parts.append("</ul>")

    parts.append("<h2>References</h2><ol class='refs' style='list-style:none;padding:0'>")
    parts += [f"<li id='ref-{e(s.id)}'>[{e(s.id)}] {_linkify(reference_text(s))}</li>" for s in refs]
    parts.append("</ol></main></body></html>")
    return "\n".join(parts)


def _linkify(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"(https?://[^\s<]+)", lambda m: f"<a href='{m.group(1)}'>{m.group(1)}</a>", escaped)


# ---------------------------------------------------------------------------
# QC reports
# ---------------------------------------------------------------------------


def _stamp(report_version: int, lesson: Lesson, reviewer: str, at: datetime) -> list[str]:
    lines = [f"Reviewed by {reviewer} on {at.day} {at:%b %Y, %H:%M} UTC. Checked lesson version {report_version}."]
    if report_version != lesson.version_number:
        lines.append(f"Note: the lesson has changed since (now version {lesson.version_number}); re-run this check for current results.")
    return lines


def _issues_md(issues) -> list[str]:
    if not issues:
        return ["No issues found.", ""]
    out = []
    for i in issues:
        status = "" if i.status == "open" else f" ({i.status}{f' in version {i.resolved_in_version}' if i.resolved_in_version else ''})"
        out.append(f"### {i.id} ({i.severity}) {i.title}{status}")
        if i.section_id:
            out.append(f"Section: {i.section_id}")
        out += [i.detail, "", f"Suggestion: {i.suggestion}", ""]
        if i.dismiss_reason:
            out += [f"Dismissed because: {i.dismiss_reason}", ""]
    return out


def facts_report_markdown(lesson: Lesson, report: FactReport) -> str:
    out = [f"# Fact check report: {lesson.request.title}", ""]
    out += _stamp(report.version, lesson, report.reviewer, report.generated_at) + [""]
    out += [f"**Accuracy: {round(report.accuracy_score * 100)}%.** {report.summary}", "", "## Issues", ""]
    out += _issues_md(report.issues)
    out += ["## Claims", "", "| Id | Claim | Section | Verdict | Evidence |", "|---|---|---|---|---|"]
    for c in report.claims:
        ev = "; ".join(f"[{x.source_id}] “{x.quote[:160]}” ({x.match.replace('_', ' ')})" for x in c.evidence) or "none"
        text = c.text.replace("|", "\\|")
        out.append(f"| {c.id} | {text} | {c.section_id} | {c.verdict.replace('_', ' ')}{' (downgraded)' if c.downgraded else ''} | {ev.replace('|', '/')} |")
    out += ["", "## Sources", "", "| Id | Source | Tier | Score | Cited | Flags |", "|---|---|---|---|---|---|"]
    for a in report.sources:
        s = lesson.source(a.source_id)
        title = (s.title if s else a.source_id).replace("|", "/")
        out.append(f"| {a.source_id} | {title} | {a.tier.replace('_', ' ')} | {a.score:.2f} | {'yes' if a.cited else 'no'} | {', '.join(a.flags) or '-'} |")
    return "\n".join(out) + "\n"


def instruction_report_markdown(lesson: Lesson, report: InstructionReport) -> str:
    out = [f"# Teaching quality report: {lesson.request.title}", ""]
    out += _stamp(report.version, lesson, report.reviewer, report.generated_at) + [""]
    out += [f"**Quality score: {report.quality_score:.0f} of 100.** {report.summary}", "", "## Objective coverage", "",
            "| Part | Statement | Taught in | Tested by | Status |", "|---|---|---|---|---|"]
    for r in report.coverage:
        out.append(f"| {r.atom_id} | {r.statement} | {', '.join(r.taught_in) or '-'} | {', '.join(r.assessed_in) or '-'} | {r.status.replace('_', ' ')} |")
    out += ["", f"## Timing ({report.total_minutes} minutes planned, about {report.estimated_total_minutes} minutes of reading)", "",
            "| Section | Allotted | Reading estimate | Words | Status |", "|---|---|---|---|---|"]
    for t in report.timing:
        out.append(f"| {t.section_id} | {t.allotted_minutes} | {t.estimated_minutes} | {t.words} | {t.status.replace('_', ' ')} |")
    out += ["", "## Rubric", "", "| Criterion | Score | Rationale |", "|---|---|---|"]
    for r in report.rubric:
        out.append(f"| {r.criterion.replace('_', ' ')} | {r.score} of 5 | {r.rationale} |")
    if report.strengths:
        out += ["", "## Strengths", ""] + [f"- {s}" for s in report.strengths]
    out += ["", "## Issues", ""] + _issues_md(report.issues)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# JSON and ZIP
# ---------------------------------------------------------------------------


def lesson_json(lesson: Lesson) -> str:
    data = lesson.model_dump(mode="json", exclude={"log"})
    data["versions"] = data["versions"][-1:]  # current version only
    for s in data["sources"]:
        s.pop("text", None)
    return json.dumps(data, indent=2, ensure_ascii=False)


def sources_json(lesson: Lesson) -> str:
    return json.dumps([s.model_dump(mode="json", exclude={"text"}) for s in lesson.sources], indent=2, ensure_ascii=False)


BUNDLE_README = """Lectern export: {title} (version {version})

lesson.md                 The lesson in Markdown with front matter, answer key and references.
lesson.html               The same lesson as a standalone web page. Open it and print to PDF if needed.
references.md             The references cited in the lesson.
qc-facts-report.md/.json  QC Layer 1: research and factual accuracy.
qc-teaching-report.md/.json  QC Layer 2: instructional quality.
sources.json              Every source found during research, with reliability scores.
"""


def bundle(lesson: Lesson) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", BUNDLE_README.format(title=lesson.request.title, version=lesson.version_number))
        z.writestr("lesson.md", lesson_markdown(lesson))
        z.writestr("lesson.html", lesson_html(lesson))
        z.writestr("references.md", references_markdown(lesson))
        if lesson.fact_report:
            z.writestr("qc-facts-report.md", facts_report_markdown(lesson, lesson.fact_report))
            z.writestr("qc-facts-report.json", lesson.fact_report.model_dump_json(indent=2))
        if lesson.instruction_report:
            z.writestr("qc-teaching-report.md", instruction_report_markdown(lesson, lesson.instruction_report))
            z.writestr("qc-teaching-report.json", lesson.instruction_report.model_dump_json(indent=2))
        z.writestr("sources.json", sources_json(lesson))
    return buffer.getvalue()
