import { useRef, type KeyboardEvent } from "react";
import type { Lesson } from "../types";
import { KIND_LABEL } from "../ui";

/** The 45-minute timeline: one segment per section, proportional to its minutes. */
export default function LessonClock({ lesson, active, onSelect }: { lesson: Lesson; active: string | null; onSelect: (id: string) => void }) {
  const sections = lesson.content?.sections ?? [];
  const timing = new Map((lesson.instruction_report?.timing ?? []).map((t) => [t.section_id, t]));
  const total = sections.reduce((sum, s) => sum + s.minutes, 0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKey(e: KeyboardEvent, index: number) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = e.key === "ArrowRight" ? Math.min(index + 1, sections.length - 1) : Math.max(index - 1, 0);
    refs.current[next]?.focus();
  }

  const estimate = lesson.instruction_report?.estimated_total_minutes;
  return (
    <div className="clock-wrap">
      <div className="clock-meta">
        <span>{total} minutes{total !== 45 ? " (should be 45)" : ""}</span>
        {estimate != null && <span>About {Math.max(1, Math.round(estimate))} minute{Math.round(estimate) === 1 ? "" : "s"} of reading; the rest is examples, practice and questions</span>}
      </div>
      <div className="clock" role="list" aria-label="Lesson timeline">
        {sections.map((s, i) => {
          const t = timing.get(s.id);
          const doing = s.kind === "activity" || s.kind === "check";
          const over = t?.status === "too_long";
          const tip = `${KIND_LABEL[s.kind]}: ${s.title}. ${s.minutes} minutes allotted${t ? `, about ${t.estimated_minutes} to read` : ""}.`;
          return (
            <button
              key={s.id}
              role="listitem"
              ref={(el) => (refs.current[i] = el)}
              className={`clock-seg${doing ? " doing" : ""}`}
              style={{ flexGrow: s.minutes, flexBasis: 0 }}
              aria-current={active === s.id}
              title={tip}
              aria-label={tip}
              onClick={() => onSelect(s.id)}
              onKeyDown={(e) => onKey(e, i)}
            >
              <span className="seg-title">{s.title}</span>
              <span className="seg-min">{s.minutes} min</span>
              {over && <span className="notch" aria-hidden="true" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
