# Demo video script (about 9 minutes)

Before recording: run the second lesson in advance; open the HTTP lesson form empty; browser zoom 110 percent; notifications off; a clean browser window. Say the lines in your own words; the wording below is a guide.

## 0:00 to 0:30, what this is

*Screen: a finished lesson in the workspace.*

"This is Lectern. It turns a lesson title and a learning objective into a 45-minute lesson where every factual sentence points to a source it actually read. Before an instructor ever sees it, it checks the lesson twice: once for facts, once for teaching quality. The instructor then reviews each finding, applies or dismisses the fix, and exports the lesson with its references and both reports."

## 0:30 to 1:15, inputs

*Screen: home page.*

"I'll use the sample from the task: HTTP Requests and Responses, with the objective 'Explain GET and POST methods and distinguish between 2xx, 4xx and 5xx response status categories.' I can set the audience and whether it's self-paced or taught in class, and paste sources I already trust. Down here it shows which model writes and which model reviews: the reviewer is a different model, so the check is independent of the author."

*Click Check connections.*

"Before spending anything, this sends one tiny real request to every service: both models, web search, YouTube, Wikipedia and the book catalogues. All green, with response times. If a key were wrong or a model had been retired, this row would say so, instead of the lesson failing five minutes in. If a model name has been retired, Lectern also finds the closest available model on its own and logs the switch."

*Click Research and write lesson.*

## 1:15 to 2:30, the pipeline

*Screen: the seven steps running. Cut the waits and say so.*

"It runs seven steps and saves after every one. First it breaks the objective into four measurable parts: explain GET, explain POST, distinguish them, and classify status codes. Then it plans the research and gathers sources: web pages through Tavily, Wikipedia, YouTube with transcripts, and books from Google Books and Open Library. Each lookup is isolated: if one search fails, it's logged as a warning and the rest carries on. I've cut the waiting here; the full run takes a few minutes."

*Optional cut-in: a failed step with its message and Retry this step.* "If a step does fail, for example an invalid key, it says exactly what happened, and Retry resumes from that step without redoing anything before it."

## 2:30 to 3:30, sources

*Screen: Sources tab.*

"Every source is ranked by authority, with the reason shown. RFC 9110, the HTTP standard, is at the top as a primary source; MDN is official documentation; a tutorial blog sits lower as unrated. Books are marked as bibliographic records, because these APIs don't give full text, so they're offered as further reading rather than treated as read. For videos it reads the transcript and finds the part that's actually about this topic, so the lesson can say 'watch 2:10 to 6:40' instead of sending a learner into a 40-minute video. The research log shows every query and anything that failed."

## 3:30 to 4:30, the lesson

*Screen: manuscript and the lesson clock.*

"This bar is the 45 minutes. Each segment is a section; the hatched ones are where the learner is doing rather than reading. The model suggests minutes, but code scales them to exactly 45, and the teaching check estimates reading time for each section. The lesson has a hook, the concepts, a worked example with real curl commands, an activity with steps and an expected result, the knowledge check, and a recap. Hovering a citation shows the exact passage from the source that the fact check verified."

## 4:30 to 5:45, the fact check

*Screen: Facts tab. Then edit the GET and POST section and add: "POST requests are idempotent." Save, click Re-check.*

"Now the first quality check. It lists every checkable claim, retrieves the best passages for each, and asks a reviewer model to judge it. The important part: the reviewer has to quote its evidence word for word, and then code checks that quote really exists in the source. If it doesn't, the claim is treated as unsupported. So the checker can't invent support.

Let me plant a mistake. I'll add 'POST requests are idempotent', save, and re-check. It's flagged as contradicted, high priority, with the sentence from RFC 9110 that lists the idempotent methods, marked as an exact match. I can preview the fix as a diff, and apply it. That's version 3 now."

## 5:45 to 6:45, the teaching check

*Screen: Teaching tab.*

"The second check is about teaching. This coverage map shows, for each part of the objective, which section teaches it and which question tests it. Here, part 2 is taught but never tested, so it suggests adding a question. Preview, and it writes one question just for that part. Apply. It also shows timing per section, a rubric with a reason for each score, and specific suggestions. The two checks never see each other's findings."

## 6:45 to 7:15, history

*Screen: History tab.*

"Every edit, fix and restore is a new version. Nothing is overwritten. I can compare any version with the current one and restore it, which itself becomes a new version."

## 7:15 to 7:45, export

*Screen: Export dialog, then open the ZIP contents.*

"Export gives a bundle: the lesson in Markdown, which fits a Markdown-based workflow, a standalone web page you can print to PDF, the references, and both QC reports in Markdown and JSON."

## 7:45 to 8:15, the second lesson

*Screen: the second lesson and docs/FACT_VERIFICATION.md.*

"Here's my second test lesson, generated the same way, with both reports. I checked the facts in both lessons myself against the primary sources; that's recorded in the repository."

## 8:15 to 9:00, how it's built

*Screen: README architecture or the decisions table.*

"It's FastAPI and Pydantic on the back end: every model reply is validated against a schema. Evidence retrieval uses BM25, which is deterministic and easy to explain. The minutes, citations, quotes and coverage are all checked in code, and the language models are used only where judgement is needed. It works with Claude, OpenAI, Gemini or OpenRouter. The interface is React and TypeScript. GitHub Actions runs the whole test suite, builds the interface and the Docker image on every push, and it can be hosted behind a passphrase with spend limits, so a shared link cannot run up the API bill. For a curriculum team, the next step would be running this from their existing Markdown workflow and in batches for a whole module. Thank you."
