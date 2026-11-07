# Architecture

## Components

```
frontend/ (React, TypeScript, Vite)
  pages/Home.tsx            new lesson form, provider status, lesson library
  pages/LessonPage.tsx      pipeline view or workspace; subscribes to server-sent events
  components/               LessonClock, Outline, Manuscript, SectionEditor (lazy), ReviewRail,
                            IssueCard (preview, diff, apply, dismiss), ExportDialog, PipelineView

backend/lectern/
  main.py                   app factory; readable validation errors; serves frontend/dist
  api.py                    REST routes and the event stream
  config.py                 settings from .env; writer and reviewer resolution; public status (no secrets)
  models.py                 every Pydantic model: requests, model-output schemas, stored records
  store.py                  SQLite, one JSON document per lesson, a lock per lesson
  events.py                 in-memory publish/subscribe for server-sent events
  exporters.py              Markdown, HTML, JSON, ZIP; reference formatting
  llm/                      structured calls with retries, validation and one repair
  research/                 providers, collector, reliability tiers, passages and BM25
  pipeline/
    steps.py                analyze, plan_research, research, outline, draft
    qc_facts.py             QC Layer 1
    qc_instruction.py       QC Layer 2
    checks.py               deterministic checks shared by both layers
    prompts.py              every prompt
    runner.py               runs steps, saves after each, merges concurrent edits, recovers on restart
    fixes.py                edits, fix preview and apply, restore; every change is a version
```

## Data flow

1. `POST /api/lessons` validates the request, stores a lesson with seven pending steps and starts the runner in the background.
2. For each step the runner marks it running, saves, runs it, stores its output on the lesson, marks it done and saves. Events are published at each change; the browser refetches the lesson.
3. On failure the step records a readable message and the run stops. Everything before it stays. `POST /api/lessons/{id}/run` with no step resumes from the first failed or pending step.
4. The draft creates version 1. Both QC reports record the version they checked.
5. Edits, fixes and restores append versions. If the instructor edits while a QC step is running, the runner keeps the edit and only attaches the new report.
6. Exports are built from the current version and the latest reports.

## Why seven steps

Each step has one job and one stored output, which makes failures local (a YouTube outage cannot lose the outline), makes retries cheap (only the failed step reruns), and makes the run easy to follow in the interface and to explain.

## Failure handling

| Layer | Behaviour |
|---|---|
| Model calls | 3 attempts with exponential backoff on timeouts, connection errors, 429 and 5xx; no retry on 400, 401, 403, 404; one repair attempt when the reply does not match the schema |
| Research | Each query and page read is isolated and logged; the step fails only when no readable source exists |
| Steps | Readable error on the step; retry from that step |
| Server restart | Steps left "running" are marked failed and can be retried |
| Edits | `base_version` must match the current version, otherwise 409 with the latest version number |
