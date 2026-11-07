import { AlertTriangle, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Lesson, StepName, StepState } from "../types";
import { useToast } from "../ui";

export default function PipelineView({ lesson, onChange }: { lesson: Lesson; onChange: (l: Lesson) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function retry(step: StepName) {
    setBusy(true);
    try {
      onChange(await api.run(lesson.id, step));
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const warnings = lesson.log.filter((l) => l.level !== "info").slice(-8);
  const failedLookups = lesson.research_log.filter((r) => !r.ok);

  return (
    <section className="pipeline" aria-live="polite">
      <h1>{lesson.request.title}</h1>
      <p className="objective">{lesson.request.objective}</p>
      <ol className="steps">
        {lesson.steps.map((step) => (
          <StepRow key={step.name} step={step} label={lesson.step_labels[step.name]} onRetry={() => retry(step.name)} busy={busy || lesson.running} />
        ))}
      </ol>
      {lesson.analysis && (
        <>
          <h2 className="subhead">Objective broken into</h2>
          <ul className="log">
            {lesson.analysis.atoms.map((a) => <li key={a.id}><strong>{a.id}</strong> {a.statement} <span style={{ color: "var(--ink-faint)" }}>({a.bloom_level})</span></li>)}
          </ul>
        </>
      )}
      {lesson.sources.length > 0 && (
        <p className="log" style={{ marginTop: 16 }}>
          {lesson.sources.length} sources gathered from {new Set(lesson.sources.map((s) => s.domain)).size} sites.
        </p>
      )}
      {(warnings.length > 0 || failedLookups.length > 0) && (
        <>
          <h2 className="subhead">Notes from this run</h2>
          <ul className="log">
            {warnings.map((w, i) => <li key={i} className={w.level}>{w.message}</li>)}
            {failedLookups.slice(0, 6).map((r, i) => <li key={`r${i}`} className="bad">{r.provider}: {r.query}: {r.error}</li>)}
          </ul>
        </>
      )}
    </section>
  );
}

function StepRow({ step, label, onRetry, busy }: { step: StepState; label: string; onRetry: () => void; busy: boolean }) {
  const elapsed = useElapsed(step);
  return (
    <li className={`step ${step.status}`}>
      <span className="icon" aria-hidden="true">
        {step.status === "done" && <Check size={12} strokeWidth={3} />}
        {step.status === "failed" && <AlertTriangle size={11} />}
      </span>
      <div>
        <div className="label">{label}<span className="visually-hidden">: {step.status}</span></div>
        {step.detail && <div className="detail">{step.detail}</div>}
        {step.error && <div className="err" role="alert">{step.error}</div>}
        {step.status === "failed" && (
          <button className="btn btn-small" style={{ marginTop: 8 }} onClick={onRetry} disabled={busy}>Retry this step</button>
        )}
      </div>
      <span className="time">{elapsed}</span>
    </li>
  );
}

function useElapsed(step: StepState): string {
  const [, tick] = useState(0);
  useEffect(() => {
    if (step.status !== "running") return;
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [step.status]);
  if (!step.started_at) return "";
  const end = step.finished_at ? new Date(step.finished_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(step.started_at).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
