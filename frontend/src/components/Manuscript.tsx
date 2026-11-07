import { Pencil } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";
import type { Issue, KnowledgeCheck, Lesson, Section, Source } from "../types";
import { KIND_LABEL, mmss, TIER_LABEL, useToast } from "../ui";
// The editor (CodeMirror) is loaded only when someone edits a section.
const SectionEditor = lazy(() => import("./SectionEditor"));

interface Props {
  lesson: Lesson;
  onChange: (l: Lesson) => void;
  onActiveSection: (id: string) => void;
  focusedSection: string | null;
  issues: Issue[];
  selectedIssue: string | null;
  onSelectIssue: (issue: Issue) => void;
  onShowSource: (id: string) => void;
}

const SAFE_FLAG_TEXT = /^[^[\]()*_`#>|\n]{12,300}$/;

/** Turn [S1, S3] citations into links the renderer shows as chips, and mark flagged claims. */
export function prepareMarkdown(body: string, flags: { id: string; text: string; high: boolean }[]): string {
  let out = body;
  for (const flag of flags) {
    if (!SAFE_FLAG_TEXT.test(flag.text)) continue;
    const at = out.indexOf(flag.text);
    if (at === -1) continue;
    out = `${out.slice(0, at)}[${flag.text}](#flag-${flag.id}${flag.high ? "-high" : ""})${out.slice(at + flag.text.length)}`;
  }
  return out.replace(/\[(S\d+(?:\s*[,;]\s*S\d+)*)\](?!\()/g, (_, group: string) =>
    group.split(/[,;]/).map((id) => `[${id.trim()}](#cite-${id.trim()})`).join(""),
  );
}

export default function Manuscript(props: Props) {
  const { lesson, onActiveSection, focusedSection } = props;
  const content = lesson.content!;
  const pageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = pageRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) onActiveSection(visible[0].target.id);
      },
      { rootMargin: "-140px 0px -55% 0px" },
    );
    root.querySelectorAll(".section").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [content.sections.length, onActiveSection]);

  const sourceMap = useMemo(() => new Map(lesson.sources.map((s) => [s.id, s])), [lesson.sources]);
  const cited = useMemo(() => {
    const ids = new Set<string>();
    const scan = (t: string) => t.replace(/\[(S\d+(?:\s*[,;]\s*S\d+)*)\]/g, (_m, g: string) => {
      g.split(/[,;]/).forEach((x) => ids.add(x.trim()));
      return "";
    });
    content.sections.forEach((s) => scan(s.body_md));
    content.knowledge_checks.forEach((k) => k.source_ids.forEach((x) => ids.add(x)));
    content.videos.forEach((v) => ids.add(v.source_id));
    return [...ids].filter((id) => sourceMap.has(id)).sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
  }, [content, sourceMap]);

  return (
    <div className="manuscript-col">
      <article className="page" ref={pageRef}>
        <h1>{lesson.request.title}</h1>
        <p className="summary">{content.summary}</p>
        <div className="objective-box">
          <strong>Learning objective.</strong> {lesson.request.objective}
        </div>
        {content.sections.map((section) => (
          <SectionBlock key={section.id} section={section} focused={focusedSection === section.id} sourceMap={sourceMap} {...props} />
        ))}
        {content.videos.length > 0 && (
          <section className="section" id="watch-next">
            <div className="section-head"><h2>Watch next</h2><span className="kind">Optional, outside the 45 minutes</span></div>
            <ul className="prose videos">
              {content.videos.map((v) => {
                const s = sourceMap.get(v.source_id);
                if (!s) return null;
                return (
                  <li key={v.source_id}>
                    <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>{" "}
                    <span style={{ color: "var(--ink-muted)", fontSize: 15 }}>
                      ({s.channel || "YouTube"}, {mmss(s.duration_seconds)})
                      {s.best_segment && <> Watch {mmss(s.best_segment.start_seconds)} to {mmss(s.best_segment.end_seconds)}.</>}
                    </span>{" "}
                    {v.why}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
        <section className="section" id="references">
          <div className="section-head"><h2>References</h2></div>
          <ol className="refs">
            {cited.map((id) => {
              const s = sourceMap.get(id)!;
              return (
                <li key={id} id={`ref-${id}`}>
                  [{id}] {s.kind === "book" && s.authors.length ? `${s.authors.join(", ")}. ` : ""}
                  <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                  {s.kind === "book" && s.publisher ? `. ${s.publisher}` : ""}
                  {s.year ? ` (${s.year})` : ""}. <span style={{ color: "var(--ink-muted)" }}>{TIER_LABEL[s.reliability.tier]}</span>
                </li>
              );
            })}
          </ol>
        </section>
      </article>
    </div>
  );
}

function SectionBlock(props: Props & { section: Section; focused: boolean; sourceMap: Map<string, Source> }) {
  const { lesson, section, issues, focused, onSelectIssue, onShowSource, sourceMap, onChange } = props;
  const [editing, setEditing] = useState(false);
  const index = lesson.content!.sections.findIndex((s) => s.id === section.id);
  const sectionIssues = issues.filter((i) => i.section_id === section.id);
  const high = sectionIssues.some((i) => i.severity === "high");

  const flags = useMemo(() => {
    const out: { id: string; text: string; high: boolean }[] = [];
    for (const issue of sectionIssues) {
      const text = issue.fix?.type === "replace" ? issue.fix.find : issue.detail.match(/^“(.+?)”/)?.[1];
      if (text) out.push({ id: issue.id, text, high: issue.severity === "high" });
    }
    return out;
  }, [sectionIssues]);

  const markdown = useMemo(() => prepareMarkdown(section.body_md, flags), [section.body_md, flags]);
  const evidence = useMemo(() => evidenceBySource(lesson, section.id), [lesson, section.id]);

  return (
    <section id={section.id} className={`section${focused ? " focused" : ""}`} aria-labelledby={`${section.id}-h`}>
      {sectionIssues.length > 0 && (
        <button
          className={`margin-flag${high ? " high" : ""}`}
          onClick={() => onSelectIssue(sectionIssues[0])}
          aria-label={`${sectionIssues.length} open findings in this section`}
          title={sectionIssues.map((i) => `${i.id}: ${i.title}`).join("\n")}
        >
          {sectionIssues.length}
        </button>
      )}
      <div className="section-head">
        <h2 id={`${section.id}-h`}>{index + 1}. {section.title}</h2>
        <span className="kind">{KIND_LABEL[section.kind]}, {section.minutes} min</span>
        {!editing && (
          <div className="section-tools">
            <button className="btn btn-quiet btn-small" onClick={() => setEditing(true)} aria-label={`Edit ${section.title}`}><Pencil /> Edit</button>
          </div>
        )}
      </div>
      {editing ? (
        <Suspense fallback={<p className="rail-summary">Opening the editor…</p>}>
          <SectionEditor lesson={lesson} section={section} onDone={() => setEditing(false)} onSaved={onChange} />
        </Suspense>
      ) : (
        <div className="prose">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => {
                if (href?.startsWith("#cite-")) {
                  const id = href.slice(6);
                  return <CitationChip id={id} source={sourceMap.get(id)} quote={evidence.get(id)} onOpen={() => onShowSource(id)} />;
                }
                if (href?.startsWith("#flag-")) {
                  const [, issueId, level] = href.split("-");
                  const issue = sectionIssues.find((i) => i.id === issueId);
                  return (
                    <mark className={level === "high" ? "flag-high" : undefined} title={issue?.title}
                      onClick={() => issue && onSelectIssue(issue)} style={{ cursor: "pointer" }}>
                      {children}
                    </mark>
                  );
                }
                return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
              },
            }}
          >
            {markdown}
          </ReactMarkdown>
          {section.kind === "check" && <Checks lesson={lesson} onChange={onChange} />}
          {section.instructor_notes && <p className="notes"><strong>Instructor notes.</strong> {section.instructor_notes}</p>}
        </div>
      )}
    </section>
  );
}

function evidenceBySource(lesson: Lesson, sectionId: string): Map<string, string> {
  const map = new Map<string, string>();
  for (const claim of lesson.fact_report?.claims ?? []) {
    if (claim.section_id !== sectionId) continue;
    for (const e of claim.evidence) {
      if ((e.match === "exact" || e.match === "close") && !map.has(e.source_id)) map.set(e.source_id, e.quote);
    }
  }
  return map;
}

function CitationChip({ id, source, quote, onOpen }: { id: string; source?: Source; quote?: string; onOpen: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number }>({ left: 0, top: 0 });
  function show() {
    const r = ref.current?.getBoundingClientRect();
    if (r) setPos({ left: Math.min(r.left + window.scrollX - 20, window.innerWidth - 400), top: r.bottom + window.scrollY + 8 });
    setOpen(true);
  }
  if (!source) return <span className="cite" title="This citation does not match any source">[{id}?]</span>;
  return (
    <span ref={ref} style={{ display: "inline" }} onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
      <button className="cite" onFocus={show} onBlur={() => setOpen(false)} onClick={onOpen} aria-label={`Source ${id}: ${source.title}`}>
        {id}
      </button>
      {open && (
        <span className="cite-pop" role="tooltip" style={{ left: pos.left, top: pos.top, position: "absolute" }}>
          <strong>{source.title}</strong>
          <br />
          <span style={{ color: "var(--ink-muted)" }}>{source.domain}, {TIER_LABEL[source.reliability.tier]}</span>
          <span className="q" style={{ display: "block" }}>{quote ? `“${quote}”` : source.snippet.slice(0, 240)}</span>
          <span style={{ display: "block", marginTop: 6, color: "var(--ink-faint)", fontSize: 12 }}>
            {quote ? "Verified passage from the fact check." : "Source summary. Click the number to see it in Sources."}
          </span>
        </span>
      )}
    </span>
  );
}

function Checks({ lesson, onChange }: { lesson: Lesson; onChange: (l: Lesson) => void }) {
  return (
    <div>
      {lesson.content!.knowledge_checks.map((k, i) => <CheckCard key={k.id} lesson={lesson} check={k} n={i + 1} onChange={onChange} />)}
    </div>
  );
}

function CheckCard({ lesson, check, n, onChange }: { lesson: Lesson; check: KnowledgeCheck; n: number; onChange: (l: Lesson) => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(check);
  useEffect(() => setDraft(check), [check]);

  async function save() {
    try {
      onChange(await api.editCheck(lesson.id, check.id, { base_version: lesson.version, question: draft.question, options: draft.options, answer_index: draft.answer_index, explanation: draft.explanation }));
      setEditing(false);
      toast(`Question saved. Lesson is now version ${lesson.version + 1}.`);
    } catch (e) {
      toast((e as Error).message, true);
    }
  }

  if (editing) {
    return (
      <div className="check">
        <label className="field"><span>Question</span>
          <textarea className="textarea" rows={2} value={draft.question} onChange={(e) => setDraft({ ...draft, question: e.target.value })} />
        </label>
        <fieldset style={{ border: 0, padding: 0, margin: "8px 0" }}>
          <legend style={{ fontSize: 13, color: "var(--ink-muted)" }}>Options (select the correct one)</legend>
          {draft.options.map((o, i) => (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
              <input type="radio" name={`ans-${check.id}`} checked={draft.answer_index === i} onChange={() => setDraft({ ...draft, answer_index: i })} aria-label={`Option ${String.fromCharCode(65 + i)} is correct`} />
              <input className="input" value={o} onChange={(e) => setDraft({ ...draft, options: draft.options.map((x, j) => (j === i ? e.target.value : x)) })} />
            </div>
          ))}
        </fieldset>
        <label className="field"><span>Explanation</span>
          <textarea className="textarea" rows={2} value={draft.explanation} onChange={(e) => setDraft({ ...draft, explanation: e.target.value })} />
        </label>
        <div className="check-tools">
          <button className="btn btn-primary btn-small" onClick={save}>Save question</button>
          <button className="btn btn-small" onClick={() => { setDraft(check); setEditing(false); }}>Cancel</button>
        </div>
      </div>
    );
  }
  return (
    <div className="check">
      <div className="qtext">Question {n}. {check.question}</div>
      <ol>
        {check.options.map((o, i) => <li key={i} className={i === check.answer_index ? "correct" : undefined}>{o}{i === check.answer_index && <span className="visually-hidden"> (correct answer)</span>}</li>)}
      </ol>
      <div className="explain">{check.explanation}</div>
      <div className="check-tools">
        <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>Tests {check.atom_ids.join(", ")}</span>
        <button className="btn btn-quiet btn-small" onClick={() => setEditing(true)}><Pencil /> Edit question</button>
      </div>
    </div>
  );
}
