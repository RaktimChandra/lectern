import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { LessonRequest } from "../types";
import { BrandMark, timeAgo } from "../ui";
import ConnectionCheck from "../components/ConnectionCheck";

const SAMPLE = {
  title: "HTTP Requests and Responses",
  objective: "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
};

export default function Home() {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand"><BrandMark />Lectern</Link>
      </header>
      <main className="home">
        <section>
          <h1>Write a lesson you can check</h1>
          <p className="lede">
            Give a title and a learning objective. Lectern researches books, web pages and videos, writes a 45-minute
            lesson with every fact cited, then reviews it for accuracy and for teaching quality.
          </p>
          <NewLessonForm />
        </section>
        <Library />
      </main>
    </>
  );
}

function NewLessonForm() {
  const navigate = useNavigate();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const [form, setForm] = useState<LessonRequest>({ title: "", objective: "", audience: "beginner", mode: "self_paced", seed_urls: [] });
  const [urls, setUrls] = useState("");
  const [errors, setErrors] = useState<{ title?: string; objective?: string; urls?: string; form?: string }>({});

  const create = useMutation({
    mutationFn: api.create,
    onSuccess: (lesson) => navigate(`/lessons/${lesson.id}`),
    onError: (err: Error) => setErrors({ form: err instanceof ApiError ? err.message : "Could not start the lesson." }),
  });

  function validate(): boolean {
    const next: typeof errors = {};
    if (!form.title.trim()) next.title = "Add a lesson title.";
    else if (form.title.replace(/[^a-z]/gi, "").length < 3) next.title = "Use a few words that describe the topic.";
    const words = form.objective.trim().split(/\s+/).filter(Boolean).length;
    if (!form.objective.trim()) next.objective = "Add a learning objective: one sentence saying what learners will be able to do.";
    else if (words < 4) next.objective = "Write the objective as a full sentence, for example: Explain GET and POST methods and…";
    const bad = urls.split("\n").map((u) => u.trim()).filter((u) => u && !/^https?:\/\//.test(u));
    if (bad.length) next.urls = `"${bad[0]}" is not a web address. It should start with https://`;
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    create.mutate({ ...form, seed_urls: urls.split("\n").map((u) => u.trim()).filter(Boolean) });
  }

  const noModel = health.data && !health.data.writer;
  const wordCount = form.objective.trim().split(/\s+/).filter(Boolean).length;

  return (
    <form className="form" onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor="title">Lesson title</label>
        <input id="title" className="input" value={form.title} placeholder={SAMPLE.title} aria-invalid={!!errors.title}
          aria-describedby={errors.title ? "title-err" : undefined}
          onChange={(e) => setForm({ ...form, title: e.target.value })} />
        {errors.title && <span id="title-err" className="field-error">{errors.title}</span>}
      </div>
      <div className="field">
        <label htmlFor="objective">Learning objective</label>
        <textarea id="objective" className="textarea" rows={3} value={form.objective} placeholder={SAMPLE.objective}
          aria-invalid={!!errors.objective} aria-describedby="objective-hint"
          onChange={(e) => setForm({ ...form, objective: e.target.value })} />
        <span id="objective-hint" className={errors.objective ? "field-error" : "hint"}>
          {errors.objective ?? `What learners will be able to do afterwards. ${wordCount ? `${wordCount} words.` : ""}`}
        </span>
      </div>
      <div className="row">
        <div className="field">
          <span id="aud" style={{ fontWeight: 600 }}>Audience</span>
          <div className="segmented" role="group" aria-labelledby="aud">
            {(["beginner", "intermediate", "advanced"] as const).map((a) => (
              <button type="button" key={a} aria-pressed={form.audience === a} onClick={() => setForm({ ...form, audience: a })}>
                {a[0].toUpperCase() + a.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <span id="del" style={{ fontWeight: 600 }}>Delivery</span>
          <div className="segmented" role="group" aria-labelledby="del">
            <button type="button" aria-pressed={form.mode === "self_paced"} onClick={() => setForm({ ...form, mode: "self_paced" })}>Self-paced</button>
            <button type="button" aria-pressed={form.mode === "instructor_led"} onClick={() => setForm({ ...form, mode: "instructor_led" })}>Instructor-led</button>
          </div>
        </div>
      </div>
      <details>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Add your own sources (optional)</summary>
        <div className="field" style={{ marginTop: 8 }}>
          <textarea className="textarea" rows={3} value={urls} aria-label="Your sources, one web address per line"
            placeholder="https://www.rfc-editor.org/rfc/rfc9110" onChange={(e) => setUrls(e.target.value)} aria-invalid={!!errors.urls} />
          <span className={errors.urls ? "field-error" : "hint"}>{errors.urls ?? "One web address per line. These are always read and cited first."}</span>
        </div>
      </details>
      {errors.form && <div className="alert" role="alert">{errors.form}</div>}
      {noModel && (
        <div className="alert alert-warn" role="alert">
          No AI model is configured. Add ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY to the .env file and restart Lectern.
        </div>
      )}
      <div>
        <button type="submit" className="btn btn-primary" disabled={create.isPending || !!noModel}>
          {create.isPending ? "Starting…" : "Research and write lesson"}
        </button>
        {!form.title && !form.objective && (
          <button type="button" className="btn btn-quiet" style={{ marginLeft: 8 }} onClick={() => setForm({ ...form, ...SAMPLE })}>
            Use the HTTP example
          </button>
        )}
      </div>
      {health.data && <ConnectionCheck health={health.data} />}
    </form>
  );
}

function Library() {
  const lessons = useQuery({ queryKey: ["lessons"], queryFn: api.lessons, refetchInterval: 5000 });
  return (
    <section className="library" aria-labelledby="lib">
      <h2 id="lib">Your lessons</h2>
      {lessons.isError && <p className="alert">{(lessons.error as Error).message}</p>}
      {lessons.data && lessons.data.length === 0 && (
        <p className="empty">No lessons yet. Write a title and an objective to create your first one.</p>
      )}
      <ul className="library-list">
        {lessons.data?.map((l) => (
          <li key={l.id} className="library-item">
            <Link to={`/lessons/${l.id}`}>
              <span className="t">{l.title}</span>
              <span className="m">
                {l.status === "running" ? "In progress" : l.status === "failed" ? "Needs a retry" : l.version ? `Version ${l.version}` : "Not started"}
                <br />
                {l.accuracy_score != null && `${Math.round(l.accuracy_score * 100)}% supported`}
                {l.quality_score != null && `, quality ${Math.round(l.quality_score)}`}
                <br />
                {timeAgo(l.updated_at)}
              </span>
              <span className="o">{l.objective}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
