import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Issue, Lesson } from "../types";
import { KIND_LABEL, mmss, TIER_LABEL, timeAgo, useToast, VerdictTag } from "../ui";
import IssueCard, { Diff } from "./IssueCard";

export type RailTab = "facts" | "teaching" | "sources" | "history";

interface Props {
  lesson: Lesson;
  tab: RailTab;
  onTab: (t: RailTab) => void;
  open: boolean;
  selectedIssue: string | null;
  onSelectIssue: (i: Issue) => void;
  highlightSource: string | null;
  onChange: (l: Lesson) => void;
}

export default function ReviewRail(props: Props) {
  const { lesson, tab, onTab, open } = props;
  const openFacts = lesson.fact_report?.issues.filter((i) => i.status === "open").length ?? 0;
  const openTeach = lesson.instruction_report?.issues.filter((i) => i.status === "open").length ?? 0;
  const tabs: [RailTab, string, number | null][] = [
    ["facts", "Facts", openFacts],
    ["teaching", "Teaching", openTeach],
    ["sources", "Sources", lesson.sources.length],
    ["history", "History", lesson.versions.length],
  ];
  const running = lesson.steps.find((s) => s.status === "running");
  return (
    <aside className={`rail${open ? " open" : ""}`} aria-label="Review">
      <div className="tabs" role="tablist">
        {tabs.map(([key, label, count]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => onTab(key)}>
            {label} {count ? <span className="count">{count}</span> : null}
          </button>
        ))}
      </div>
      <div className="rail-body" role="tabpanel">
        {running && <p className="stale">{lesson.step_labels[running.name]}…</p>}
        {tab === "facts" && <FactsPanel {...props} />}
        {tab === "teaching" && <TeachingPanel {...props} />}
        {tab === "sources" && <SourcesPanel {...props} />}
        {tab === "history" && <HistoryPanel {...props} />}
      </div>
    </aside>
  );
}

function StaleNote({ lesson, checked, layer, onChange }: { lesson: Lesson; checked: number; layer: "facts" | "instruction"; onChange: (l: Lesson) => void }) {
  const toast = useToast();
  if (checked === lesson.version) return null;
  return (
    <div className="stale">
      <span>Checked version {checked}; the lesson is now version {lesson.version}.</span>
      <button className="btn btn-small" disabled={lesson.running} onClick={async () => {
        try { onChange(await api.recheck(lesson.id, layer)); } catch (e) { toast((e as Error).message, true); }
      }}>Re-check</button>
    </div>
  );
}

function IssueList({ issues, ...props }: Props & { issues: Issue[] }) {
  const [filter, setFilter] = useState<"open" | "all">("open");
  const shown = filter === "open" ? issues.filter((i) => i.status === "open") : issues;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector(".issue.selected")?.scrollIntoView({ block: "nearest" });
  }, [props.selectedIssue]);
  return (
    <div ref={ref}>
      <div className="filters">
        <button aria-pressed={filter === "open"} onClick={() => setFilter("open")}>Open ({issues.filter((i) => i.status === "open").length})</button>
        <button aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All ({issues.length})</button>
      </div>
      {shown.length === 0 && <p className="rail-summary">{issues.length ? "Every finding has been applied or dismissed." : "No findings."}</p>}
      {shown.map((issue) => (
        <IssueCard key={issue.id} lesson={props.lesson} issue={issue} selected={props.selectedIssue === issue.id}
          onSelect={() => props.onSelectIssue(issue)} onChange={props.onChange} />
      ))}
    </div>
  );
}

function ApplyExact({ lesson, issues, onChange }: { lesson: Lesson; issues: Issue[]; onChange: (l: Lesson) => void }) {
  const toast = useToast();
  const count = issues.filter((i) => i.status === "open" && i.fix?.type === "replace").length;
  if (count < 2) return null;
  return (
    <button className="btn btn-small" disabled={lesson.running} onClick={async () => {
      try {
        const next = await api.applyExact(lesson.id, lesson.version);
        onChange(next);
        toast(`Applied ${next.applied.length} exact fixes. Lesson is now version ${next.version}.`);
      } catch (e) { toast((e as Error).message, true); }
    }}>Apply all {count} exact fixes</button>
  );
}

function FactsPanel(props: Props) {
  const { lesson } = props;
  const report = lesson.fact_report;
  const [claimFilter, setClaimFilter] = useState<"attention" | "all">("attention");
  if (!report) return <p className="rail-summary">The fact check runs after the lesson is written.</p>;
  const claims = claimFilter === "all" ? report.claims : report.claims.filter((c) => c.verdict !== "supported");
  const sectionTitle = (id: string) => lesson.content?.sections.find((s) => s.id === id)?.title ?? id;
  return (
    <>
      <div className="rail-head">
        <span className="score">{Math.round(report.accuracy_score * 100)}%</span>
        <span className="score-label">of checkable claims supported</span>
      </div>
      <p className="rail-summary">{report.summary}</p>
      <StaleNote lesson={lesson} checked={report.version} layer="facts" onChange={props.onChange} />
      <ApplyExact lesson={lesson} issues={report.issues} onChange={props.onChange} />
      <h3 className="subhead">Findings</h3>
      <IssueList {...props} issues={report.issues} />
      <h3 className="subhead">Claims checked against sources</h3>
      <div className="filters">
        <button aria-pressed={claimFilter === "attention"} onClick={() => setClaimFilter("attention")}>Needs attention</button>
        <button aria-pressed={claimFilter === "all"} onClick={() => setClaimFilter("all")}>All {report.claims.length}</button>
      </div>
      {claims.map((c) => (
        <div className="claim" key={c.id}>
          <VerdictTag verdict={c.verdict} /> <span className="match">{c.id}, {sectionTitle(c.section_id)}</span>
          <p className="claim-text">{c.text}</p>
          {c.note && <p className="ev">{c.note}</p>}
          {c.evidence.map((e, i) => (
            <p className="ev" key={i}>
              [{e.source_id}] <q>{e.quote}</q>{" "}
              <span className={`match${e.match === "not_found" || e.match === "no_text" ? " bad" : ""}`}>
                {e.match === "exact" ? "exact match in source" : e.match === "close" ? `close match (${e.match_score})` : e.match === "no_text" ? "source has no text to check" : "quote not found in source"}
              </span>
            </p>
          ))}
        </div>
      ))}
      <p className="reviewer">Reviewed by {report.reviewer}, {timeAgo(report.generated_at)}.</p>
    </>
  );
}

function TeachingPanel(props: Props) {
  const { lesson } = props;
  const report = lesson.instruction_report;
  if (!report) return <p className="rail-summary">The teaching review runs after the fact check.</p>;
  const title = (id: string) => {
    const i = lesson.content?.sections.findIndex((s) => s.id === id) ?? -1;
    return i >= 0 ? `${i + 1}` : id;
  };
  const max = Math.max(...report.timing.map((t) => Math.max(t.allotted_minutes, t.estimated_minutes)), 1);
  return (
    <>
      <div className="rail-head">
        <span className="score">{Math.round(report.quality_score)}</span>
        <span className="score-label">teaching quality, out of 100</span>
      </div>
      <p className="rail-summary">{report.summary}</p>
      <StaleNote lesson={lesson} checked={report.version} layer="instruction" onChange={props.onChange} />
      <h3 className="subhead">Objective coverage</h3>
      <table className="coverage">
        <thead><tr><th>Part</th><th>Taught in section</th><th>Tested by</th></tr></thead>
        <tbody>
          {report.coverage.map((r) => (
            <tr key={r.atom_id}>
              <td title={r.statement}><strong>{r.atom_id}</strong> <span style={{ color: "var(--ink-muted)" }}>{r.statement}</span></td>
              <td className={r.taught_in.length ? "" : "gap"}>{r.taught_in.length ? r.taught_in.map(title).join(", ") : "not taught"}</td>
              <td className={r.assessed_in.length ? "" : "gap"}>{r.assessed_in.length ? r.assessed_in.map((k) => k.replace("kc-", "Q")).join(", ") : "not tested"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3 className="subhead">Timing: minutes allotted and reading estimate</h3>
      {report.timing.map((t) => {
        const s = lesson.content?.sections.find((x) => x.id === t.section_id);
        return (
          <div className="timing-row" key={t.section_id} title={`${t.words} words, about ${t.estimated_minutes} min to read, ${t.allotted_minutes} min allotted`}>
            <span>{title(t.section_id)}. {s?.title} <span style={{ color: "var(--ink-faint)" }}>({s ? KIND_LABEL[s.kind] : ""})</span></span>
            <div className="bar" aria-label={`${t.estimated_minutes} of ${t.allotted_minutes} minutes`}>
              <span className={`fill${t.status === "too_long" ? " over" : ""}`} style={{ width: `${(Math.min(t.estimated_minutes, max) / max) * 100}%` }} />
              <span className="tick" style={{ left: `${(t.allotted_minutes / max) * 100}%` }} />
            </div>
          </div>
        );
      })}
      <h3 className="subhead">Rubric</h3>
      {report.rubric.map((r) => (
        <div className="rubric-row" key={r.criterion}>
          <span>{r.criterion.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}</span>
          <span className="pips" aria-label={`${r.score} of 5`}>{[1, 2, 3, 4, 5].map((n) => <i key={n} className={n <= r.score ? "on" : ""} />)}</span>
          <span className="why">{r.rationale}</span>
        </div>
      ))}
      {report.readability.flesch_reading_ease != null && (
        <p className="rail-summary" style={{ marginTop: 12 }}>
          Reading ease {report.readability.flesch_reading_ease} (Flesch), average sentence {report.readability.avg_sentence_words} words.
        </p>
      )}
      {report.strengths.length > 0 && (
        <>
          <h3 className="subhead">Worth keeping</h3>
          <ul style={{ paddingLeft: 18, fontSize: 13, margin: 0 }}>{report.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </>
      )}
      <h3 className="subhead">Findings</h3>
      <ApplyExact lesson={lesson} issues={report.issues} onChange={props.onChange} />
      <IssueList {...props} issues={report.issues} />
      <p className="reviewer">Reviewed by {report.reviewer}, {timeAgo(report.generated_at)}.</p>
    </>
  );
}

const KIND_GROUPS: [string, string][] = [["instructor", "Your sources"], ["web", "Web"], ["encyclopedia", "Encyclopedia"], ["book", "Books"], ["video", "Videos"]];

function SourcesPanel({ lesson, highlightSource }: Props) {
  const assessments = useMemo(() => new Map((lesson.fact_report?.sources ?? []).map((a) => [a.source_id, a])), [lesson.fact_report]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (highlightSource) ref.current?.querySelector(`#src-${highlightSource}`)?.scrollIntoView({ block: "center" });
  }, [highlightSource]);
  const failed = lesson.research_log.filter((r) => !r.ok);
  return (
    <div ref={ref}>
      <p className="rail-summary">
        {lesson.sources.length} sources. Ranked by authority: standards and official documentation first, community posts last.
      </p>
      {KIND_GROUPS.map(([kind, label]) => {
        const list = lesson.sources.filter((s) => s.kind === kind);
        if (!list.length) return null;
        return (
          <div key={kind}>
            <h3 className="subhead">{label}</h3>
            {list.map((s) => {
              const a = assessments.get(s.id);
              return (
                <div className={`source${highlightSource === s.id ? " hl" : ""}`} id={`src-${s.id}`} key={s.id}>
                  <div className="source-title">
                    <span style={{ color: "var(--ink-faint)" }}>{s.id}</span>
                    <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                  </div>
                  <div className="source-meta">
                    <span className={`tier ${s.reliability.tier}`}>{TIER_LABEL[s.reliability.tier]}</span>{" "}
                    {s.kind === "video" ? `${s.channel ?? ""}, ${mmss(s.duration_seconds)}` : s.kind === "book" ? [s.authors.join(", "), s.publisher, s.year].filter(Boolean).join(", ") : s.domain}
                  </div>
                  {s.best_segment && <div className="source-meta">Most relevant part: {mmss(s.best_segment.start_seconds)} to {mmss(s.best_segment.end_seconds)}</div>}
                  <div className="flags">{s.reliability.reasons.join(". ")}{a?.flags.length ? `. ${a.flags.join(". ")}.` : ""}</div>
                </div>
              );
            })}
          </div>
        );
      })}
      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600 }}>Research log ({lesson.research_log.length} lookups{failed.length ? `, ${failed.length} failed` : ""})</summary>
        <ul className="log" style={{ paddingLeft: 16 }}>
          {lesson.research_log.map((r, i) => (
            <li key={i} className={r.ok ? "" : "bad"}>{r.provider}: {r.query} {r.ok ? `(${r.results})` : `failed: ${r.error}`}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function HistoryPanel({ lesson, onChange }: Props) {
  const toast = useToast();
  const [compare, setCompare] = useState<{ number: number; text: string } | null>(null);
  const current = (lesson.content?.sections ?? []).map((s) => `## ${s.title}\n${s.body_md}`).join("\n\n");

  async function show(n: number) {
    try {
      const v = await api.version(lesson.id, n);
      setCompare({ number: n, text: v.content.sections.map((s) => `## ${s.title}\n${s.body_md}`).join("\n\n") });
    } catch (e) { toast((e as Error).message, true); }
  }

  async function restore(n: number) {
    if (!window.confirm(`Restore version ${n}? This creates a new version; nothing is deleted.`)) return;
    try {
      const next = await api.restore(lesson.id, n, lesson.version);
      onChange(next);
      setCompare(null);
      toast(`Version ${n} restored as version ${next.version}.`);
    } catch (e) { toast((e as Error).message, true); }
  }

  return (
    <>
      <p className="rail-summary">Every edit, fix and restore creates a new version. Nothing is overwritten.</p>
      <ul className="history" style={{ listStyle: "none", padding: 0 }}>
        {[...lesson.versions].reverse().map((v) => (
          <li key={v.number}>
            <span className="vn">{v.number}</span>
            <div>
              <div>{v.reason}</div>
              <div className="when">{timeAgo(v.created_at)}{v.number === lesson.version ? ", current" : ""}</div>
              {v.number !== lesson.version && (
                <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                  <button className="btn btn-small" onClick={() => show(v.number)}>Compare with current</button>
                  <button className="btn btn-small btn-quiet" onClick={() => restore(v.number)}>Restore</button>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
      {compare && (
        <>
          <h3 className="subhead">Version {compare.number} compared with version {lesson.version}</h3>
          <div className="diff" style={{ maxHeight: 420 }}><Diff before={compare.text} after={current} /></div>
        </>
      )}
    </>
  );
}
