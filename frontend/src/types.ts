// Mirrors the backend models served by /api (see backend/lectern/models.py).

export type StepName =
  | "analyze" | "plan_research" | "research" | "outline" | "draft" | "qc_facts" | "qc_instruction";
export type StepStatus = "pending" | "running" | "done" | "failed" | "skipped";
export type Severity = "high" | "medium" | "low";
export type SectionKind = "hook" | "concept" | "example" | "activity" | "check" | "recap";
export type Verdict = "supported" | "partially_supported" | "unsupported" | "contradicted";

export interface StepState {
  name: StepName;
  status: StepStatus;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  detail: string;
  attempts: number;
}

export interface LogLine { at: string; step: StepName | null; level: "info" | "warn" | "error"; message: string }

export interface LessonRequest {
  title: string;
  objective: string;
  audience: "beginner" | "intermediate" | "advanced";
  mode: "self_paced" | "instructor_led";
  seed_urls: string[];
}

export interface ObjectiveAtom { id: string; statement: string; verb: string; bloom_level: string; key_terms: string[] }

export interface Reliability { tier: string; score: number; reasons: string[] }

export interface Source {
  id: string;
  kind: "web" | "encyclopedia" | "book" | "video" | "instructor";
  title: string;
  url: string;
  domain: string;
  publisher: string;
  authors: string[];
  year: number | null;
  snippet: string;
  reliability: Reliability;
  found_by: string;
  isbn: string | null;
  duration_seconds: number | null;
  channel: string | null;
  view_count: number | null;
  has_transcript: boolean;
  best_segment: { start_seconds: number; end_seconds: number; excerpt: string } | null;
  has_full_text: boolean;
}

export interface Section {
  id: string;
  kind: SectionKind;
  title: string;
  minutes: number;
  atom_ids: string[];
  body_md: string;
  instructor_notes: string;
}

export interface KnowledgeCheck {
  id: string;
  atom_ids: string[];
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
  source_ids: string[];
}

export interface LessonContent {
  summary: string;
  sections: Section[];
  knowledge_checks: KnowledgeCheck[];
  videos: { source_id: string; why: string }[];
}

export interface Fix { type: "replace" | "rewrite" | "add_check"; find: string | null; replace: string | null; instruction: string | null }

export interface Issue {
  id: string;
  layer: "facts" | "instruction";
  severity: Severity;
  category: string;
  section_id: string | null;
  title: string;
  detail: string;
  suggestion: string;
  fix: Fix | null;
  atom_id: string | null;
  status: "open" | "applied" | "dismissed";
  resolved_in_version: number | null;
  dismiss_reason: string | null;
}

export interface Evidence { source_id: string; quote: string; match: "exact" | "close" | "not_found" | "no_text"; match_score: number }

export interface ClaimCheck {
  id: string;
  section_id: string;
  text: string;
  cited_source_ids: string[];
  verdict: Verdict;
  evidence: Evidence[];
  note: string;
  corrected_text: string | null;
  downgraded: boolean;
}

export interface FactReport {
  version: number;
  generated_at: string;
  reviewer: string;
  claims: ClaimCheck[];
  sources: { source_id: string; tier: string; score: number; cited: boolean; flags: string[] }[];
  issues: Issue[];
  accuracy_score: number;
  summary: string;
}

export interface InstructionReport {
  version: number;
  generated_at: string;
  reviewer: string;
  coverage: { atom_id: string; statement: string; taught_in: string[]; assessed_in: string[]; status: string }[];
  timing: { section_id: string; allotted_minutes: number; estimated_minutes: number; words: number; status: "ok" | "too_long" | "too_short" }[];
  total_minutes: number;
  estimated_total_minutes: number;
  readability: { flesch_reading_ease: number | null; avg_sentence_words: number; long_sentences: number; words: number };
  rubric: { criterion: string; score: number; rationale: string }[];
  strengths: string[];
  issues: Issue[];
  quality_score: number;
  summary: string;
}

export interface Lesson {
  id: string;
  created_at: string;
  updated_at: string;
  request: LessonRequest;
  steps: StepState[];
  step_labels: Record<StepName, string>;
  log: LogLine[];
  running: boolean;
  analysis: { atoms: ObjectiveAtom[]; prerequisites: string[]; misconceptions: string[]; scope_notes: string } | null;
  sources: Source[];
  research_log: { provider: string; query: string; ok: boolean; results: number; error: string | null }[];
  version: number;
  versions: { number: number; created_at: string; reason: string }[];
  content: LessonContent | null;
  fact_report: FactReport | null;
  instruction_report: InstructionReport | null;
}

export interface LessonSummary {
  id: string;
  title: string;
  objective: string;
  created_at: string;
  updated_at: string;
  status: "running" | "failed" | "ready" | "pending";
  version: number;
  accuracy_score: number | null;
  quality_score: number | null;
}

export interface Health {
  writer: { provider: string; model: string } | null;
  reviewer: { provider: string; model: string } | null;
  independent_reviewer: boolean;
  research: { web_search: string | null; wikipedia: boolean; youtube: boolean; books: string };
  lesson_minutes: number;
  access_protected?: boolean;
}

export interface PreflightCheck {
  name: string;
  role: "required" | "recommended" | "keyless";
  ok: boolean;
  detail: string;
  ms: number;
}

export interface FixPreview {
  kind: "section" | "check";
  section_id: string | null;
  before: string;
  after: string;
  method: "exact" | "rewrite";
  change_summary: string;
  check: Record<string, unknown> | null;
  base_version: number;
}
