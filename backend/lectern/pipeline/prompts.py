"""Every prompt Lectern sends, in one place.

Each function returns `(system, user)`. Prompts give the model a role, the
inputs, the rules and the output contract. They never ask the model to do
arithmetic (minutes are normalised in code) or to write references (built in
code from the sources actually cited).
"""

from __future__ import annotations

from ..models import (
    KnowledgeCheck,
    LessonContent,
    LessonRequest,
    ObjectiveAnalysisOut,
    OutlineSection,
    Section,
    Source,
)

HOUSE_STYLE = """House style for all lesson text:
- Write for a first-year engineering student. Short sentences. Plain words. Define each term the first time it appears.
- Use active voice and the second person ("you send a request").
- No filler or hype. Never use: "In today's world", "Let's dive in", "delve", "unlock", "embark", "seamless",
  "robust", "crucial", "game-changer", "in conclusion". No emoji. No exclamation marks outside quoted output.
- Use concrete examples from the topic with real syntax. Put code in fenced blocks with a language tag.
- Every factual statement in a concept or example section ends with a citation such as [S3] or [S2, S5] pointing
  to a source in the evidence pack that actually says it. If the evidence does not support a statement, leave it out.
- Never cite a source for something it does not say. Never invent a source id."""

AUDIENCE = {
    "beginner": "beginners (first- or second-year engineering students new to the topic)",
    "intermediate": "intermediate learners who know the basics and want depth",
    "advanced": "advanced learners who want precise, technical detail",
}
MODE = {
    "self_paced": "self-paced: the learner works alone, so every activity needs an answer they can check",
    "instructor_led": "instructor-led: a teacher runs it in class, so add facilitation notes",
}


def _atoms(analysis: ObjectiveAnalysisOut) -> str:
    return "\n".join(
        f"- {a.id} ({a.bloom_level}): {a.statement}  [key terms: {', '.join(a.key_terms) or 'none'}]"
        for a in analysis.atoms
    )


def _source_line(s: Source) -> str:
    extra = ""
    if s.kind == "video":
        extra = f", {_mmss(s.duration_seconds)}" if s.duration_seconds else ""
        extra += ", transcript available" if s.has_transcript else ", no transcript"
    if s.kind == "book":
        extra = ", bibliographic record only"
    return f"[{s.id}] {s.title} ({s.kind}, {s.reliability.tier.replace('_', ' ')}{extra})"


def _mmss(seconds: int | None) -> str:
    if seconds is None:
        return "?"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def analyze(req: LessonRequest) -> tuple[str, str]:
    system = (
        "You are a senior instructional designer. You turn a learning objective into measurable parts "
        "that a 45-minute lesson can teach and test."
    )
    user = f"""Lesson title: {req.title}
Learning objective: {req.objective}
Audience: {AUDIENCE[req.audience]}.
Delivery: {MODE[req.mode]}.

Break the objective into its measurable parts. Each part describes one thing a learner can be observed doing,
starts with an action verb taken from the objective where possible, and carries a Bloom's level. Stay inside the
objective: do not add topics it does not ask for. Number the parts O1, O2 and so on.
Also list the prerequisites the learner needs, the misconceptions learners commonly hold about this topic,
and a short scope note saying what is in and out of scope for 45 minutes.
For each part give key terms that a search engine would match."""
    return system, user


def plan_research(req: LessonRequest, analysis: ObjectiveAnalysisOut) -> tuple[str, str]:
    system = (
        "You plan research for a lesson. You know which organisations publish the authoritative material for "
        "a topic: standards bodies, official documentation, universities and respected publishers."
    )
    user = f"""Lesson: {req.title}
Objective: {req.objective}
Objective parts:
{_atoms(analysis)}

Write 4 to 8 web search queries that together cover every objective part. Prefer queries likely to surface
standards and official documentation, and say which parts each query serves.
Write 2 or 3 YouTube queries for short explainer videos a {req.audience} learner would find clear.
Write 1 to 3 book search queries (title-style keywords).
Suggest up to 3 exact English Wikipedia article titles.
List the authoritative domains for this topic (for example rfc-editor.org for internet protocols)."""
    return system, user


def outline(req: LessonRequest, analysis: ObjectiveAnalysisOut, sources: list[Source], minutes: int,
            problem: str | None = None) -> tuple[str, str]:
    system = (
        f"You design {minutes}-minute lessons that work for self-study and for a teacher in a classroom.\n{HOUSE_STYLE}"
    )
    source_lines = "\n".join(_source_line(s) for s in sources[:30])
    misconceptions = "\n".join(f"- {m}" for m in analysis.misconceptions) or "- none listed"
    retry = f"\n\nYour previous plan had a problem: {problem}. Fix it." if problem else ""
    user = f"""Lesson: {req.title}
Objective: {req.objective}
Audience: {AUDIENCE[req.audience]}. Delivery: {MODE[req.mode]}.
Objective parts:
{_atoms(analysis)}
Misconceptions to address:
{misconceptions}
Scope: {analysis.scope_notes or 'not specified'}
Sources available:
{source_lines}

Plan 5 to 8 sections that together take {minutes} minutes. Section kinds:
- hook: a short opener built on a concrete situation that makes the learner want the answer
- concept: explains one idea
- example: works through a real case step by step
- activity: the learner does something and can check the result
- check: the knowledge-check questions
- recap: what to remember and what comes next
Start with a hook and end with a recap. Include at least one concept, one example, one activity and exactly one
check. Give each section the objective parts it serves: every part must be taught in a concept, example or
activity section, and the check section must list every part. Suggest minutes per section; the application
scales them to exactly {minutes}. Write a one or two sentence plan for each section.{retry}"""
    return system, user


def draft(req: LessonRequest, analysis: ObjectiveAnalysisOut, sections: list[OutlineSection],
          evidence: dict[int, list[tuple[str, str, str]]], videos: list[Source], wpm: int) -> tuple[str, str]:
    system = (
        "You are writing a lesson for a university curriculum team. It will be checked sentence by sentence "
        f"against the evidence below, so accuracy matters more than length.\n{HOUSE_STYLE}"
    )
    plan_lines = []
    for i, s in enumerate(sections):
        plan_lines.append(f"[{i}] {s.kind}, {s.minutes} min, parts {' '.join(s.atom_ids) or '-'}: {s.title}. {s.plan}")
    evidence_blocks = []
    for i, items in evidence.items():
        if not items:
            continue
        block = [f"--- Evidence for section [{i}] ---"]
        for source_id, label, text in items:
            block.append(f"[{source_id}] {label}\n\"{text}\"")
        evidence_blocks.append("\n".join(block))
    video_lines = "\n".join(
        f"[{v.id}] {v.title} ({v.channel or 'unknown channel'}, {_mmss(v.duration_seconds)}"
        + (f", most relevant {_mmss(v.best_segment.start_seconds)} to {_mmss(v.best_segment.end_seconds)}" if v.best_segment else "")
        + ")"
        for v in videos
    ) or "none"
    misconceptions = "\n".join(f"- {m}" for m in analysis.misconceptions) or "- none listed"
    notes_rule = (
        "Delivery is instructor-led: for every section add instructor_notes with a timing cue, one question to ask "
        "the room, and the most common wrong answer to listen for."
        if req.mode == "instructor_led"
        else "Delivery is self-paced: leave instructor_notes empty."
    )
    user = f"""Lesson: {req.title}
Objective: {req.objective}
Audience: {AUDIENCE[req.audience]}.
Objective parts:
{_atoms(analysis)}
Misconceptions to address:
{misconceptions}

Sections to write (keep this order; index each draft by the number in brackets):
{chr(10).join(plan_lines)}

{chr(10).join(evidence_blocks) or 'No evidence passages were retrieved.'}

Videos you may recommend:
{video_lines}

Write:
1. summary: two sentences telling the learner what they will be able to do after this lesson.
2. sections: a Markdown body for every section index above. Do not repeat the section title as a heading.
   Match the length to the minutes: about {wpm} words per reading minute for hook, concept, example and recap;
   activity and check sections need less text and more doing. Concept and example sections cite every factual
   statement. Address the listed misconceptions where they fit. The activity has numbered steps, an expected
   result and a way for the learner to check their work. The check section body is one or two sentences of
   instructions only; the questions go in knowledge_checks. {notes_rule}
3. knowledge_checks: 4 to 6 multiple-choice questions, each with exactly 4 options. Each tests one or more objective parts, has exactly one
   correct answer, uses a misconception as a distractor where possible, and has an explanation of why the answer
   is right and why the most tempting wrong option is wrong. Test every objective part at least once. List the
   source ids that support each answer.
4. videos: up to 3 of the listed videos that best support the lesson, each with one sentence on why it helps.
Do not write a references list; the application adds it from your citations."""
    return system, user


# ---------------------------------------------------------------------------
# QC Layer 1
# ---------------------------------------------------------------------------

REVIEWER_RULE = "You are independent of the author. Judge only what is in front of you."


def extract_claims(content: LessonContent) -> tuple[str, str]:
    system = (
        "You are a fact-checking editor. You list every checkable factual claim in a lesson so each can be verified "
        f"against sources. You do not judge the claims yet. {REVIEWER_RULE}"
    )
    body = "\n\n".join(f"[{i}] {s.kind}: {s.title}\n{s.body_md}" for i, s in enumerate(content.sections))
    user = f"""Lesson sections:
{body}

List the factual claims in the order they appear, one per item. A claim is a statement that could be true or false:
definitions, how something works, numbers, codes, behaviours, dates, comparisons. Split sentences that contain two
claims. Mark analogies, instructions to the learner, opinions and learning tips as checkable=false. Copy the claim
text as closely as possible from the lesson so it can be found in the section. Include the source ids cited next to
the claim. Return at most 30 claims; if there are more, keep the ones most important to the lesson's objective."""
    return system, user


def judge_claims(batch: list[tuple[int, str, list[str], list[tuple[str, str, str]]]]) -> tuple[str, str]:
    system = f"""You verify claims strictly against the passages provided. Use only these passages, not your own knowledge.
A claim is:
- supported: a passage states it, or states something that directly implies it;
- partially_supported: a passage supports part of it, or the claim is stronger or broader than the passage allows;
- unsupported: no passage says it, even if you believe it is true;
- contradicted: a passage says something incompatible with it.
For every verdict except unsupported, copy the exact sentence or sentences from the passage that justify it into
evidence.quote, word for word, and give the source id. The application checks every quote against the source text;
a quote that is not verbatim does not count. If the claim is wrong or overstated, give corrected_text that the
evidence would support, written in the same style as the lesson. {REVIEWER_RULE}"""
    parts = []
    for index, claim, cited, passages in batch:
        lines = [f"Claim {index}: \"{claim}\" (cited: {', '.join(cited) or 'none'})", "Passages:"]
        for pid, label, text in passages:
            lines.append(f"[{pid}] ({label}) \"{text}\"")
        if not passages:
            lines.append("(no passages found)")
        parts.append("\n".join(lines))
    user = "\n\n".join(parts) + "\n\nReturn one judgement per claim, using the claim numbers above as claim_index."
    return system, user


def fact_review(req: LessonRequest, content: LessonContent, sources: list[Source]) -> tuple[str, str]:
    system = (
        "You are a senior technical reviewer. You read a whole lesson for accuracy problems that a claim-by-claim "
        f"check misses. {REVIEWER_RULE}"
    )
    body = "\n\n".join(f"[{i}] {s.kind}: {s.title}\n{s.body_md}" for i, s in enumerate(content.sections))
    checks = _checks_text(content.knowledge_checks)
    user = f"""Lesson: {req.title}
Objective: {req.objective}
Sections:
{body}

Knowledge checks:
{checks}

Sources:
{chr(10).join(_source_line(s) for s in sources[:30])}

Report only real problems, each with the section index (or null for the whole lesson), a severity and a concrete
suggestion:
- misleading simplifications or framing: true sentences that leave a false impression;
- inconsistencies between sections, or between the text, examples, code and knowledge-check answers;
- outdated information, such as obsolete standard numbers or deprecated practices;
- facts the objective needs that the lesson leaves out;
- examples or code that would not work as shown;
- a knowledge-check answer that is wrong or has two defensible answers.
Return an empty list if there are none. Do not give style or teaching feedback; another reviewer does that."""
    return system, user


# ---------------------------------------------------------------------------
# QC Layer 2
# ---------------------------------------------------------------------------


def instruction_review(req: LessonRequest, analysis: ObjectiveAnalysisOut, content: LessonContent,
                       automated: str) -> tuple[str, str]:
    system = (
        "You are an experienced instructional designer reviewing a 45-minute lesson for a university curriculum team. "
        f"You judge teaching quality only; a separate reviewer checks facts. {REVIEWER_RULE}"
    )
    body = "\n\n".join(
        f"[{i}] {s.kind}, {s.minutes} min, parts {' '.join(s.atom_ids) or '-'}: {s.title}\n{s.body_md}"
        + (f"\nInstructor notes: {s.instructor_notes}" if s.instructor_notes else "")
        for i, s in enumerate(content.sections)
    )
    user = f"""Lesson: {req.title}
Objective: {req.objective}
Audience: {AUDIENCE[req.audience]}. Delivery: {MODE[req.mode]}.
Objective parts:
{_atoms(analysis)}

Automated findings (already computed; do not repeat them as issues):
{automated}

Lesson:
Summary: {content.summary}
{body}

Knowledge checks:
{_checks_text(content.knowledge_checks)}

Score each criterion from 1 to 5 (5 = ready for students without changes, 3 = usable after small edits,
1 = needs rewriting), with a one-sentence rationale:
objective_alignment (every part taught and tested at the level the objective asks for),
clarity (a learner could follow it alone; terms defined on first use),
structure_and_flow (each section builds on the last; the hook connects to the recap),
examples_and_practice (realistic examples; an activity that makes the learner apply the idea),
engagement (concrete scenarios; the learner does something regularly),
accuracy_of_level (the depth fits the audience and the time).
Then list at most 12 specific issues that would most improve learning, most important first. For each: section
index (or null), category (one of: alignment, clarity, structure, examples, practice, engagement, assessment,
pacing, level, accessibility), severity (high, medium or low), what is wrong, and a concrete suggestion. If a small text change fixes it, give the exact
text to find in that section (copied exactly, at least a few words) and its replacement.
Finally list up to 5 strengths worth keeping."""
    return system, user


def _checks_text(checks: list[KnowledgeCheck]) -> str:
    lines = []
    for k in checks:
        opts = " | ".join(f"{chr(65 + i)}. {o}" for i, o in enumerate(k.options))
        lines.append(
            f"{k.id} (parts {' '.join(k.atom_ids)}): {k.question}\n  Options: {opts}\n"
            f"  Answer: {chr(65 + k.answer_index)}. Explanation: {k.explanation}"
        )
    return "\n".join(lines) or "none"


# ---------------------------------------------------------------------------
# Fixes
# ---------------------------------------------------------------------------


def rewrite_section(section: Section, finding: str, suggestion: str, instruction: str | None,
                    evidence: list[tuple[str, str, str]]) -> tuple[str, str]:
    system = (
        "You revise one section of a lesson to fix a specific reviewer finding. Change only what the finding requires. "
        "Keep the section's purpose, its length within 15 percent, its tone, and every citation that still applies. "
        f"Add citations only to sources in the evidence given.\n{HOUSE_STYLE}"
    )
    ev = "\n".join(f"[{sid}] {label}\n\"{text}\"" for sid, label, text in evidence) or "none"
    user = f"""Section: {section.title} ({section.kind}, {section.minutes} min)
Current text:
{section.body_md}

Finding: {finding}
Suggested improvement: {suggestion}
{('Instruction: ' + instruction) if instruction else ''}

Relevant evidence:
{ev}

Return the full revised section text (Markdown, without the section title) and a one-sentence summary of what changed."""
    return system, user


def add_check(req: LessonRequest, atom_statement: str, atom_id: str, content: LessonContent,
              evidence: list[tuple[str, str, str]]) -> tuple[str, str]:
    system = (
        "You write one multiple-choice knowledge check for a lesson. It has exactly one correct answer, plausible "
        f"distractors based on real misconceptions, and an explanation.\n{HOUSE_STYLE}"
    )
    taught = "\n\n".join(f"{s.title}:\n{s.body_md}" for s in content.sections if atom_id in s.atom_ids)
    ev = "\n".join(f"[{sid}] {label}\n\"{text}\"" for sid, label, text in evidence) or "none"
    user = f"""Lesson: {req.title}
Write one question that tests objective part {atom_id}: {atom_statement}
It must be answerable from what the lesson teaches:
{taught or content.summary}

Evidence:
{ev}

Use atom_ids ["{atom_id}"], 4 options, and list the supporting source ids."""
    return system, user
