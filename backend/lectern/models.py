"""Domain models shared by the pipeline, the API and the exporters.

Two families live here:

* **LLM output schemas** (`*Out`): the exact JSON shapes the models are asked to
  return. They are validated with Pydantic, so a malformed reply never leaks
  into the lesson.
* **Stored records**: what the app persists and serves — the lesson, its
  sources, its versions and both QC reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

Audience = Literal["beginner", "intermediate", "advanced"]
DeliveryMode = Literal["self_paced", "instructor_led"]


class LessonRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=600)
    audience: Audience = "beginner"
    mode: DeliveryMode = "self_paced"
    seed_urls: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title", "objective")
    @classmethod
    def _strip_and_require(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("cannot be empty")
        return value

    @field_validator("title")
    @classmethod
    def _title_needs_letters(cls, value: str) -> str:
        if sum(ch.isalpha() for ch in value) < 3:
            raise ValueError("needs at least a few words describing the topic")
        return value

    @field_validator("objective")
    @classmethod
    def _objective_is_a_sentence(cls, value: str) -> str:
        if len(value.split()) < 4:
            raise ValueError("should be a full sentence describing what learners will be able to do")
        return value

    @field_validator("seed_urls")
    @classmethod
    def _valid_urls(cls, urls: list[str]) -> list[str]:
        cleaned = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"'{url}' is not a web address (it should start with https://)")
            cleaned.append(url)
        return cleaned


# ---------------------------------------------------------------------------
# Step 1: objective analysis
# ---------------------------------------------------------------------------

BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]


class ObjectiveAtom(BaseModel):
    id: str = Field(description="Stable id such as O1, O2")
    statement: str = Field(description="One measurable thing the learner must be able to do")
    verb: str = Field(description="The action verb, e.g. explain, distinguish")
    bloom_level: BloomLevel
    key_terms: list[str] = Field(default_factory=list)


class ObjectiveAnalysisOut(BaseModel):
    atoms: list[ObjectiveAtom] = Field(min_length=1, max_length=8)
    prerequisites: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(
        default_factory=list, description="Common learner misconceptions worth addressing"
    )
    scope_notes: str = Field(default="", description="What is in and out of scope for 45 minutes")


# ---------------------------------------------------------------------------
# Step 2: research plan
# ---------------------------------------------------------------------------


class ResearchQuery(BaseModel):
    query: str
    purpose: str
    atom_ids: list[str] = Field(default_factory=list)


class ResearchPlanOut(BaseModel):
    web_queries: list[ResearchQuery] = Field(min_length=1, max_length=8)
    video_queries: list[str] = Field(min_length=1, max_length=4)
    book_queries: list[str] = Field(min_length=1, max_length=3)
    wikipedia_titles: list[str] = Field(default_factory=list, max_length=4)
    authoritative_domains: list[str] = Field(
        default_factory=list,
        description="Domains whose content is primary/official for this topic, e.g. rfc-editor.org",
    )


# ---------------------------------------------------------------------------
# Step 3: sources
# ---------------------------------------------------------------------------

SourceKind = Literal["web", "encyclopedia", "book", "video", "instructor"]
ReliabilityTier = Literal["primary", "official_docs", "academic", "reference", "publisher", "community", "unknown"]


class Reliability(BaseModel):
    tier: ReliabilityTier
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class VideoSegment(BaseModel):
    start_seconds: int
    end_seconds: int
    excerpt: str


class Source(BaseModel):
    id: str  # S1, S2 ...
    kind: SourceKind
    title: str
    url: str
    domain: str = ""
    publisher: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    snippet: str = ""
    text: str = ""  # extracted full text or transcript; used for evidence checks
    reliability: Reliability
    found_by: str = ""  # the query that surfaced it
    retrieved_at: datetime = Field(default_factory=utcnow)
    # kind-specific
    isbn: str | None = None
    duration_seconds: int | None = None
    channel: str | None = None
    view_count: int | None = None
    has_transcript: bool = False
    best_segment: VideoSegment | None = None

    @property
    def has_full_text(self) -> bool:
        return len(self.text) > 400


class ResearchLogEntry(BaseModel):
    provider: str
    query: str
    ok: bool
    results: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# Step 4/5: outline and draft
# ---------------------------------------------------------------------------

SectionKind = Literal["hook", "concept", "example", "activity", "check", "recap"]


class OutlineSection(BaseModel):
    kind: SectionKind
    title: str
    minutes: int = Field(ge=1, le=45)
    atom_ids: list[str] = Field(default_factory=list)
    plan: str = Field(description="What this section does, in one or two sentences")


class OutlineOut(BaseModel):
    sections: list[OutlineSection] = Field(min_length=4, max_length=10)


class SectionDraft(BaseModel):
    index: int = Field(description="0-based index of the outline section this drafts")
    body_md: str = Field(description="Markdown body. Cite sources inline as [S1], [S2].")
    instructor_notes: str = Field(default="", description="Facilitation tips for instructor-led delivery")


class KnowledgeCheckOut(BaseModel):
    atom_ids: list[str] = Field(min_length=1)
    question: str
    options: list[str] = Field(min_length=3, max_length=5)
    answer_index: int = Field(ge=0)
    explanation: str
    source_ids: list[str] = Field(default_factory=list)

    @field_validator("answer_index")
    @classmethod
    def _answer_in_range(cls, value: int, info) -> int:
        options = info.data.get("options") or []
        if options and value >= len(options):
            raise ValueError("answer_index must point to one of the options")
        return value


class VideoPickOut(BaseModel):
    source_id: str
    why: str = Field(description="Why this video helps, in one sentence")


class DraftOut(BaseModel):
    summary: str = Field(description="Two-sentence lesson overview for the learner")
    sections: list[SectionDraft]
    knowledge_checks: list[KnowledgeCheckOut] = Field(min_length=2, max_length=8)
    videos: list[VideoPickOut] = Field(default_factory=list, max_length=4)


# ---------------------------------------------------------------------------
# Stored lesson content
# ---------------------------------------------------------------------------


class Section(BaseModel):
    id: str  # sec-1 ...
    kind: SectionKind
    title: str
    minutes: int
    atom_ids: list[str] = Field(default_factory=list)
    body_md: str
    instructor_notes: str = ""


class KnowledgeCheck(BaseModel):
    id: str  # kc-1 ...
    atom_ids: list[str]
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    source_ids: list[str] = Field(default_factory=list)


class VideoPick(BaseModel):
    source_id: str
    why: str


class LessonContent(BaseModel):
    summary: str
    sections: list[Section]
    knowledge_checks: list[KnowledgeCheck]
    videos: list[VideoPick] = Field(default_factory=list)

    def section(self, section_id: str) -> Section | None:
        return next((s for s in self.sections if s.id == section_id), None)

    @property
    def total_minutes(self) -> int:
        return sum(s.minutes for s in self.sections)


# ---------------------------------------------------------------------------
# QC
# ---------------------------------------------------------------------------

Severity = Literal["high", "medium", "low"]
QCLayer = Literal["facts", "instruction"]
IssueStatus = Literal["open", "applied", "dismissed"]


class Fix(BaseModel):
    """A machine-applicable fix.

    `replace` is an exact find-and-replace done in code; `rewrite` asks the writer
    model to revise one section; `add_check` asks it to write one new question.
    """

    type: Literal["replace", "rewrite", "add_check"]
    find: str | None = None
    replace: str | None = None
    instruction: str | None = None


class Issue(BaseModel):
    id: str  # F1.. for facts, I1.. for instruction
    layer: QCLayer
    severity: Severity
    category: str
    section_id: str | None = None
    title: str
    detail: str
    suggestion: str
    fix: Fix | None = None
    atom_id: str | None = None  # for coverage issues
    status: IssueStatus = "open"
    resolved_in_version: int | None = None
    dismiss_reason: str | None = None


# Facts layer -----------------------------------------------------------------

ClaimVerdict = Literal["supported", "partially_supported", "unsupported", "contradicted"]
QuoteMatch = Literal["exact", "close", "not_found", "no_text"]


class ClaimOut(BaseModel):
    section_index: int
    text: str = Field(description="The claim, quoted or closely paraphrased from the lesson")
    cited_source_ids: list[str] = Field(default_factory=list)
    checkable: bool = Field(default=True, description="False for opinions, instructions or analogies")


class ClaimsOut(BaseModel):
    claims: list[ClaimOut] = Field(max_length=40)


class EvidenceOut(BaseModel):
    source_id: str
    quote: str = Field(description="Verbatim sentence copied from the passage")


class ClaimJudgementOut(BaseModel):
    claim_index: int
    verdict: ClaimVerdict
    evidence: list[EvidenceOut] = Field(default_factory=list, max_length=3)
    note: str = Field(default="", description="What is wrong or missing, if anything")
    corrected_text: str | None = Field(default=None, description="A corrected version of the claim, if needed")


class ClaimJudgementsOut(BaseModel):
    judgements: list[ClaimJudgementOut]


class Evidence(BaseModel):
    source_id: str
    quote: str
    match: QuoteMatch
    match_score: float = 0.0


class ClaimCheck(BaseModel):
    id: str  # C1 ...
    section_id: str
    text: str
    cited_source_ids: list[str]
    verdict: ClaimVerdict
    evidence: list[Evidence]
    note: str = ""
    corrected_text: str | None = None
    downgraded: bool = Field(default=False, description="Verdict lowered because evidence could not be confirmed")


class SourceAssessment(BaseModel):
    source_id: str
    tier: ReliabilityTier
    score: float
    cited: bool
    flags: list[str] = Field(default_factory=list)


class FactGapOut(BaseModel):
    section_index: int | None = None
    title: str
    detail: str
    severity: Severity
    suggestion: str


class FactReviewOut(BaseModel):
    """Holistic accuracy review: misleading framing, inconsistencies, gaps."""

    gaps: list[FactGapOut] = Field(default_factory=list, max_length=12)


class FactReport(BaseModel):
    version: int
    generated_at: datetime = Field(default_factory=utcnow)
    reviewer: str
    claims: list[ClaimCheck]
    sources: list[SourceAssessment]
    issues: list[Issue]
    accuracy_score: float = Field(description="Share of checkable claims that are supported (partial counts half)")
    summary: str


# Instruction layer -----------------------------------------------------------


class CoverageRow(BaseModel):
    atom_id: str
    statement: str
    taught_in: list[str]
    assessed_in: list[str]
    status: Literal["covered", "taught_not_assessed", "assessed_not_taught", "missing"]


class SectionTiming(BaseModel):
    section_id: str
    allotted_minutes: int
    estimated_minutes: float
    words: int
    status: Literal["ok", "too_long", "too_short"]


class RubricScoreOut(BaseModel):
    criterion: Literal[
        "objective_alignment",
        "clarity",
        "structure_and_flow",
        "examples_and_practice",
        "engagement",
        "accuracy_of_level",
    ]
    score: int = Field(ge=1, le=5)
    rationale: str


class InstructionIssueOut(BaseModel):
    section_index: int | None = None
    category: Literal["alignment", "clarity", "structure", "examples", "practice", "assessment", "pacing", "level", "accessibility"]
    severity: Severity
    title: str
    detail: str
    suggestion: str
    find: str | None = Field(default=None, description="Exact text in the section to replace, if a small edit fixes it")
    replace: str | None = None


class InstructionReviewOut(BaseModel):
    rubric: list[RubricScoreOut] = Field(min_length=6, max_length=6)
    issues: list[InstructionIssueOut] = Field(default_factory=list, max_length=15)
    strengths: list[str] = Field(default_factory=list, max_length=5)


class InstructionReport(BaseModel):
    version: int
    generated_at: datetime = Field(default_factory=utcnow)
    reviewer: str
    coverage: list[CoverageRow]
    timing: list[SectionTiming]
    total_minutes: int
    estimated_total_minutes: float
    readability: dict
    rubric: list[RubricScoreOut]
    strengths: list[str]
    issues: list[Issue]
    quality_score: float
    summary: str


# ---------------------------------------------------------------------------
# Fixes and versions
# ---------------------------------------------------------------------------


class RewriteOut(BaseModel):
    body_md: str
    change_summary: str


class Version(BaseModel):
    number: int
    created_at: datetime = Field(default_factory=utcnow)
    reason: str
    content: LessonContent


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------


class StepName(str, Enum):
    analyze = "analyze"
    plan_research = "plan_research"
    research = "research"
    outline = "outline"
    draft = "draft"
    qc_facts = "qc_facts"
    qc_instruction = "qc_instruction"


STEP_ORDER: list[StepName] = list(StepName)

STEP_LABELS: dict[StepName, str] = {
    StepName.analyze: "Break down the objective",
    StepName.plan_research: "Plan the research",
    StepName.research: "Gather sources",
    StepName.outline: "Plan 45 minutes",
    StepName.draft: "Write the lesson",
    StepName.qc_facts: "Check facts",
    StepName.qc_instruction: "Review teaching quality",
}

StepStatus = Literal["pending", "running", "done", "failed", "skipped"]


class StepState(BaseModel):
    name: StepName
    status: StepStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    detail: str = ""
    attempts: int = 0


class LogLine(BaseModel):
    at: datetime = Field(default_factory=utcnow)
    step: StepName | None = None
    level: Literal["info", "warn", "error"] = "info"
    message: str


class Lesson(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    request: LessonRequest
    steps: list[StepState] = Field(default_factory=lambda: [StepState(name=s) for s in STEP_ORDER])
    log: list[LogLine] = Field(default_factory=list)
    running: bool = False

    analysis: ObjectiveAnalysisOut | None = None
    research_plan: ResearchPlanOut | None = None
    sources: list[Source] = Field(default_factory=list)
    research_log: list[ResearchLogEntry] = Field(default_factory=list)
    outline: OutlineOut | None = None

    versions: list[Version] = Field(default_factory=list)
    fact_report: FactReport | None = None
    instruction_report: InstructionReport | None = None

    @property
    def current(self) -> Version | None:
        return self.versions[-1] if self.versions else None

    @property
    def version_number(self) -> int:
        return self.versions[-1].number if self.versions else 0

    def step(self, name: StepName) -> StepState:
        return next(s for s in self.steps if s.name == name)

    def source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.id == source_id), None)

    def all_issues(self) -> list[Issue]:
        issues: list[Issue] = []
        if self.fact_report:
            issues.extend(self.fact_report.issues)
        if self.instruction_report:
            issues.extend(self.instruction_report.issues)
        return issues

    def issue(self, issue_id: str) -> Issue | None:
        return next((i for i in self.all_issues() if i.id == issue_id), None)
