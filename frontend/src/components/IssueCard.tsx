import { diffWords } from "diff";
import { useState } from "react";
import { api } from "../api";
import type { FixPreview, Issue, Lesson } from "../types";
import { SeverityTag, useToast } from "../ui";

export default function IssueCard({ lesson, issue, selected, onSelect, onChange }: {
  lesson: Lesson; issue: Issue; selected: boolean; onSelect: () => void; onChange: (l: Lesson) => void;
}) {
  const toast = useToast();
  const [preview, setPreview] = useState<FixPreview | null>(null);
  const [edited, setEdited] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "apply" | "dismiss" | null>(null);
  const done = issue.status !== "open";
  const sectionTitle = lesson.content?.sections.find((s) => s.id === issue.section_id)?.title;

  async function run<T>(kind: typeof busy, fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(kind);
    try {
      return await fn();
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(null);
    }
  }

  async function doPreview() {
    const result = await run("preview", () => api.preview(lesson.id, issue.id));
    if (result) {
      setPreview(result);
      setEdited(null);
    }
  }

  async function doApply() {
    if (!preview) return;
    const next = await run("apply", () =>
      api.apply(lesson.id, issue.id, { base_version: preview.base_version, after: edited ?? preview.after, check: preview.check }),
    );
    if (next) {
      onChange(next);
      setPreview(null);
      toast(`Fix applied. Lesson is now version ${next.version}.`);
    }
  }

  async function doDismiss() {
    const reason = window.prompt("Why dismiss this finding? (optional)") ?? undefined;
    const next = await run("dismiss", () => api.dismiss(lesson.id, issue.id, reason));
    if (next) {
      onChange(next);
      toast(`${issue.id} dismissed.`);
    }
  }

  async function doReopen() {
    const next = await run("dismiss", () => api.reopen(lesson.id, issue.id));
    if (next) onChange(next);
  }

  return (
    <article className={`issue${selected ? " selected" : ""}${done ? " done" : ""}`} aria-labelledby={`${issue.id}-t`}>
      <div className="issue-head" onClick={onSelect} role="button" tabIndex={0} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect()}>
        <span className="issue-id">{issue.id}</span>
        <span className="issue-title" id={`${issue.id}-t`}>{issue.title}</span>
        <SeverityTag severity={issue.severity} />
      </div>
      {(selected || !done) && (
        <div className="issue-body">
          {sectionTitle && <p style={{ color: "var(--ink-faint)" }}>In {sectionTitle}</p>}
          <p>{issue.detail}</p>
          <p><strong>Suggestion.</strong> {issue.suggestion}</p>
        </div>
      )}
      {done && (
        <p className="status-note">
          {issue.status === "applied" ? `Applied in version ${issue.resolved_in_version}.` : `Dismissed${issue.dismiss_reason ? `: ${issue.dismiss_reason}` : "."}`}
          {issue.status === "dismissed" && <button className="btn btn-quiet btn-small" onClick={doReopen}>Reopen</button>}
        </p>
      )}
      {!done && preview && (
        <>
          <div className="diff" aria-label="Proposed change">
            {edited === null ? <Diff before={preview.before} after={preview.after} /> : null}
            {edited !== null && (
              <textarea className="textarea" style={{ minHeight: 200, fontFamily: "var(--serif)" }} value={edited} onChange={(e) => setEdited(e.target.value)} aria-label="Edit the fix before applying" />
            )}
          </div>
          <p className="status-note">{preview.method === "exact" ? "Exact replacement, made in code." : `Rewritten by the writer model: ${preview.change_summary}`}</p>
        </>
      )}
      {!done && (
        <div className="issue-actions">
          {issue.fix && !preview && (
            <button className="btn btn-small" onClick={doPreview} disabled={!!busy || lesson.running}>
              {busy === "preview" ? (issue.fix.type === "replace" ? "Preparing…" : "Rewriting…") : "Preview fix"}
            </button>
          )}
          {preview && (
            <>
              <button className="btn btn-small btn-primary" onClick={doApply} disabled={!!busy}>{busy === "apply" ? "Applying…" : "Apply fix"}</button>
              {preview.kind === "section" && edited === null && <button className="btn btn-small" onClick={() => setEdited(preview.after)}>Edit before applying</button>}
              <button className="btn btn-small btn-quiet" onClick={() => { setPreview(null); setEdited(null); }}>Cancel</button>
            </>
          )}
          {!preview && <button className="btn btn-small btn-quiet" onClick={doDismiss} disabled={!!busy}>Dismiss</button>}
        </div>
      )}
    </article>
  );
}

export function Diff({ before, after }: { before: string; after: string }) {
  const parts = diffWords(before, after);
  return (
    <>
      {parts.map((p, i) => (p.added ? <ins key={i}>{p.value}</ins> : p.removed ? <del key={i}>{p.value}</del> : <span key={i}>{p.value}</span>))}
    </>
  );
}
