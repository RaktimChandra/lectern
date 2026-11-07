# Sample output (live runs, 7 November 2026)

Both lessons were generated live with Gemini (writing and checking), Tavily web search, YouTube Data API v3, Wikipedia, Google Books and Open Library, then exported from Lectern unchanged.

| Lesson | Sources | Fact check (QC 1) | Teaching check (QC 2) |
|---|---|---|---|
| [HTTP Requests and Responses](http-requests-and-responses/lesson.md) (the task's sample input) | 24 (14 web, 2 encyclopedia, 2 books, 6 videos) | 22 of 29 checkable claims supported, 6 partly supported, 1 unsupported | 5 of 5 objective parts taught and tested; rubric average 5.0 of 5 |
| [Retrieval-Augmented Generation (RAG) Fundamentals](rag-fundamentals/lesson.md) (my choice) | 29 (14 web, 3 encyclopedia, 6 books, 6 videos) | 14 of 15 checkable claims supported, 1 unsupported | 4 of 4 objective parts taught and tested; rubric average 4.5 of 5 |

Each folder holds what the **Export ZIP** button produces: `lesson.md`, `lesson.html` (print to PDF from a browser), `references.md`, both QC reports as Markdown and JSON, and `sources.json`.

The HTTP lesson is at version 3. Version 2 was a test of the fact check: the sentence "POST requests are idempotent, so sending the same POST twice is always safe." was added to the GET/POST section and re-checked. QC 1 marked it **contradicted**, with two quotes it verified word for word in the sources (S11: "The POST method is not idempotent…" and S15). Version 3 restores version 1, and its report is the one exported here.

The partly supported and unsupported findings are left in the reports on purpose: they are what an instructor would review next, and they show the check does not simply approve the writer's work.
