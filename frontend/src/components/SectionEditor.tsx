import { markdown } from "@codemirror/lang-markdown";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Lesson, Section } from "../types";
import { useToast } from "../ui";

/** Markdown editor for one section. Unsaved text survives a page refresh (sessionStorage). */
export default function SectionEditor({ lesson, section, onDone, onSaved }: {
  lesson: Lesson; section: Section; onDone: () => void; onSaved: (l: Lesson) => void;
}) {
  const toast = useToast();
  const key = `lectern:draft:${lesson.id}:${section.id}`;
  const stored = readDraft(key);
  const [body, setBody] = useState(stored?.body ?? section.body_md);
  const [title, setTitle] = useState(stored?.title ?? section.title);
  const [minutes, setMinutes] = useState(stored?.minutes ?? section.minutes);
  const [notes, setNotes] = useState(stored?.notes ?? section.instructor_notes);
  const [saving, setSaving] = useState(false);
  const dirty = body !== section.body_md || title !== section.title || minutes !== section.minutes || notes !== section.instructor_notes;

  useEffect(() => {
    if (dirty) sessionStorage.setItem(key, JSON.stringify({ body, title, minutes, notes }));
  }, [body, title, minutes, notes, dirty, key]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  async function save() {
    if (!body.trim()) {
      toast("A section cannot be empty. Delete its text and write something new, or cancel.", true);
      return;
    }
    setSaving(true);
    try {
      const next = await api.editSection(lesson.id, section.id, {
        base_version: lesson.version, body_md: body, title,
        minutes: minutes !== section.minutes ? minutes : undefined,
        instructor_notes: notes,
      });
      sessionStorage.removeItem(key);
      onSaved(next);
      onDone();
      toast(`Section saved. Lesson is now version ${next.version}.`);
    } catch (e) {
      const message = e instanceof ApiError && e.status === 409
        ? "This lesson changed since you opened it. Your text is still here: copy it, reload the page, and paste it back."
        : (e as Error).message;
      toast(message, true);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    if (dirty && !window.confirm("Discard your changes to this section?")) return;
    sessionStorage.removeItem(key);
    onDone();
  }

  return (
    <div className="editor">
      <div className="editor-bar" style={{ borderTop: 0, borderBottom: "1px solid var(--rule-soft)" }}>
        <label style={{ flex: 1 }}>Title
          <input className="input" style={{ padding: "4px 8px" }} value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>Minutes
          <input type="number" min={2} max={40} value={minutes} onChange={(e) => setMinutes(Number(e.target.value) || section.minutes)} />
        </label>
      </div>
      <CodeMirror
        value={body}
        onChange={setBody}
        extensions={[markdown(), EditorView.lineWrapping]}
        basicSetup={{ lineNumbers: false, foldGutter: false, highlightActiveLine: false }}
        aria-label={`Text of ${section.title}`}
        autoFocus
      />
      {lesson.request.mode === "instructor_led" && (
        <div className="editor-bar">
          <label style={{ flex: 1 }}>Instructor notes
            <input className="input" style={{ padding: "4px 8px" }} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>
      )}
      <div className="editor-bar">
        <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>
          Markdown. Cite sources as [S1]. {minutes !== section.minutes ? "Other sections will be rebalanced so the lesson stays at 45 minutes." : ""}
        </span>
        <span className="spacer" />
        <button className="btn btn-small" onClick={cancel}>Cancel</button>
        <button className="btn btn-small btn-primary" onClick={save} disabled={saving || !dirty}>{saving ? "Saving…" : "Save section"}</button>
      </div>
    </div>
  );
}

function readDraft(key: string): { body: string; title: string; minutes: number; notes: string } | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
