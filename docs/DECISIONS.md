# Design decisions

Each entry: the decision, why, and what was rejected.

| # | Decision | Why | Rejected |
|---|---|---|---|
| 1 | Python 3.11+ backend with FastAPI and Pydantic v2 | Pydantic models double as the JSON schemas sent to the model, so every reply is validated; async I/O suits parallel research | Node full stack |
| 2 | React + TypeScript + Vite frontend | The review flow (margin markers, diffs, an editor, live progress) needs real component state; TypeScript catches API shape errors | Streamlit: fast to start but cannot do inline findings and diffs well |
| 3 | Plain CSS with design tokens instead of a CSS framework | The interface is small; one stylesheet with named tokens is easier to read and keeps the look specific | Tailwind (the original plan); a component kit |
| 4 | One process in production: FastAPI serves the built frontend | One command to run, no CORS setup for the evaluator | Two services |
| 5 | SQLite, one JSON document per lesson | Zero setup, atomic writes, easy to inspect; a lesson is naturally one document | Postgres; loose JSON files |
| 6 | Provider-neutral LLM layer: Anthropic Messages API and any OpenAI-compatible API (OpenAI, Gemini, OpenRouter, Ollama) | Works with whatever key is available, including Gemini's free tier | A framework such as LangChain: more to explain, less control over retries and validation |
| 7 | Structured output everywhere: forced tool call on Anthropic, JSON mode plus schema elsewhere, Pydantic validation, one repair attempt | Malformed output never reaches the lesson; failures are explicit and retryable | Parsing free text |
| 8 | Separate writer and reviewer settings | Lets the QC layers run on a different model from the author | One model for everything |
| 9 | Research: Tavily (or Brave), Wikipedia, YouTube Data API with transcripts, Google Books and Open Library, instructor URLs | Covers websites, books and videos; keyless sources keep it useful with few keys | Scraping search result pages |
| 10 | trafilatura for page text | Strips navigation and ads, so evidence passages are clean | Raw `get_text()` |
| 11 | BM25 over ~900-character passages | Deterministic, explainable, no extra key; suits keyword-heavy technical topics | Embeddings (extra key, harder to explain why a passage was chosen) |
| 12 | Reviewer must quote evidence; code verifies the quote is in the source (exact, or fuzzy 90+) and lowers the verdict if not | The single strongest guard against a reviewer inventing support | Trusting the reviewer's verdict |
| 13 | Minutes proposed by the model, normalised in code to exactly 45 (largest remainder, minimum 2) | The 45-minute rule is hard; models are unreliable at arithmetic | Asking the model to "make it 45" |
| 14 | Reading time estimated in code (180 wpm plus 0.12 min per code line) | Flags sections whose text cannot fit their minutes | No timing check |
| 15 | Objective split into measurable parts; sections and questions tagged with them | Makes alignment measurable as a coverage map | Judging alignment only by opinion |
| 16 | References built by code from what is cited | No invented references; every link is real | Model-written bibliography |
| 17 | Video segments from transcripts ("watch 2:10 to 6:40") | A 45-minute lesson cannot send learners into a 40-minute video | Linking whole videos |
| 18 | Books treated as bibliographic records and labelled so | Full text is not available through these APIs; pretending otherwise would be dishonest | Claiming the books were read |
| 19 | Every change is a new version; edits carry the version they started from (409 on conflict) | Saved work and edits are never lost or silently overwritten | A single mutable document |
| 20 | Reports record the version they checked and show "out of date" with Re-check | Nobody mistakes an old report for a current one | Silently stale reports |
| 21 | Fixes previewed as a word diff; exact replacements done in code, larger fixes rewrite only the target section | Instructor control; small fixes are instant and deterministic | Auto-applying suggestions |
| 22 | Server-Sent Events for progress, polling as fallback | One-directional, simple, proxy-friendly | WebSockets |
| 23 | Steps as asyncio background tasks in the server process; interrupted runs marked failed on restart | Enough for a local single-user tool; no queue to install | Celery or Redis |
| 24 | Offline test suite with recorded responses and a scripted model | Fast, free, repeatable, runs without keys | Tests that need live keys |
| 25 | Exports: Markdown, standalone HTML with print styles, JSON, ZIP bundle | Markdown matches a Markdown-in-VS-Code workflow; HTML prints to PDF without server-side PDF dependencies | Server-side PDF generation |
| 26 | No mock or replay mode in the interface | The demo must show real research and real model calls | A canned "demo mode" |
| 27 | Local-first; hosting optional and locked by default when used | The task does not require hosting. When it is hosted, an access passphrase, per-client rate limits and security headers stop strangers spending the API keys (see 31) | Mandatory hosting; an open public URL |
| 28 | Model discovery on 404: list the provider's models, pick the best general text model, remember the choice | Providers retire model names on short notice (the original default, `gemini-2.5-flash`, was on Google’s 2026 shutdown schedule). A retired default now costs one extra request instead of a failed lesson | Hard-coding a model list that goes stale |
| 29 | Request adaptation: when a 400 names `max_tokens`, `temperature`, `reasoning_effort` or `response_format`, adjust and resend, and remember it for later calls | Newer OpenAI-compatible models reject some classic parameters; the same code then works across model generations | One code path per model family |
| 30 | A connection check (`POST /api/preflight`) that sends one tiny real request to every configured service | A wrong key, a disabled API or a retired model is found in seconds, with the service named, before a lesson is started | Finding out halfway through a run |
| 31 | Hosting guard as one middleware: passphrase checked with a constant-time compare and kept as a hashed HttpOnly, SameSite=Strict cookie; sliding-window limits (new lessons per hour, model calls per hour, requests per minute); 512 KB body limit; strict CSP and other security headers | EventSource cannot send headers, so a cookie keeps live progress working; the limits cap what a leaked link can cost | Full user accounts (more to build and explain than a single-team tool needs); no protection |
| 32 | GitHub Actions CI: backend tests on Python 3.11 to 3.13, frontend type check, tests and build, then a Docker build with a smoke test of the passphrase guard | Every push proves the project still installs, builds and passes from a clean machine | Testing only on my laptop |
