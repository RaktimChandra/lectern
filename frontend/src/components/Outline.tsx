import type { Issue, Lesson } from "../types";

export default function Outline({ lesson, active, onSelect, issues }: {
  lesson: Lesson; active: string | null; onSelect: (id: string) => void; issues: Issue[];
}) {
  const sections = lesson.content?.sections ?? [];
  return (
    <nav className="outline" aria-label="Sections">
      <h2>Sections</h2>
      <ol>
        {sections.map((s, i) => {
          const count = issues.filter((x) => x.section_id === s.id).length;
          return (
            <li key={s.id}>
              <button aria-current={active === s.id} onClick={() => onSelect(s.id)}>
                <span className="n">{i + 1}</span>
                <span>{s.title}</span>
                <span className="mins">{s.minutes}m</span>
                {count > 0 && <span className="flags">{count} open finding{count > 1 ? "s" : ""}</span>}
              </button>
            </li>
          );
        })}
      </ol>
      {lesson.analysis && (
        <div className="objective">
          <strong>Objective parts</strong>
          <ul style={{ paddingLeft: 16, margin: 0 }}>
            {lesson.analysis.atoms.map((a) => <li key={a.id}><b>{a.id}</b> {a.statement}</li>)}
          </ul>
        </div>
      )}
    </nav>
  );
}
