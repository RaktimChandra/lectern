# How the two quality checks work

## QC Layer 1: research and factual accuracy

1. **Claims.** The reviewer model lists checkable factual claims (definitions, behaviours, numbers, comparisons) in reading order, at most 30. Analogies, instructions and opinions are excluded.
2. **Evidence retrieval.** All source text is split into passages of about 900 characters with one sentence of overlap and indexed with BM25. Each claim gets its five best passages, always including the best passage from each source it cites.
3. **Judgement.** In batches of six, the reviewer marks each claim supported, partially supported, unsupported or contradicted, using only the passages given, and copies its evidence verbatim.
4. **Quote verification (code).** Each quote is normalised (Unicode, quotes, dashes, whitespace, case) and searched in the full source text. A verbatim match is `exact`; a RapidFuzz partial ratio of 90 or more is `close`; anything else is `not_found`.
5. **Verdict rules (code).** Supported, partially supported and contradicted verdicts with no verified quote become **unsupported**, with a note saying the evidence could not be found.
6. **Citation integrity (code).** Citations to sources that do not exist (high); concept or example sections with no citations (medium); claims supported only by sources with reliability below 0.55 (low); claims whose verified evidence comes from a different source than the one cited (low, with a fix that changes the citation).
7. **Source review (code).** Tier, score and flags for every source: not cited, bibliographic record only, no transcript to check, low reliability, weak match to the topic.
8. **Whole-lesson review.** Misleading simplifications, inconsistencies between sections or between text and answers, outdated facts, omissions the objective needs, and examples that would not work.
9. **Findings.** Contradicted claims are high severity; unsupported medium; partially supported low. When the reviewer gives a corrected version and the claim is found verbatim in the section, the fix is an exact replacement; otherwise the writer rewrites that section with the finding as its instruction.
10. **Score.** (supported + 0.5 × partially supported) / checkable claims.

## QC Layer 2: instructional quality

Measured in code:

| Check | Rule |
|---|---|
| Total time | Section minutes sum to 45 |
| Section timing | Reading estimate = prose words ÷ 180 + 0.12 × code lines. Hook, concept, example, recap: too long above allotted × 1.3 + 0.5; too short when allotted ≥ 4 and estimate below 30 percent. Activity and check: too long above 60 percent of allotted (time is for doing) |
| Coverage | Every objective part taught in a concept, example or activity section and tested by a question |
| Structure | Worked example, activity, recap and at least two questions present |
| Activity | Numbered steps and an expected result or self-check |
| Questions | Explanations of at least 12 words; distinct options |
| Readability | Flesch reading ease on prose; flags sections below 30 or with three or more sentences over 30 words |
| Code blocks | Language tag present |
| Videos and references | A video recommended when available; at least three sources cited |

Judged by the reviewer model, given the measured results so it does not repeat them: six rubric criteria scored 1 to 5 with rationales (objective alignment, clarity, structure and flow, examples and practice, engagement, accuracy of level), specific issues with suggestions (and exact text replacements where a small edit fixes it), and strengths to keep.

Score out of 100: 70 × rubric average ÷ 5 + 20 × share of parts fully covered + 10 × share of sections whose timing fits.

## Independence

- Separate prompts and inputs; neither layer sees the other's findings or the writer's reasoning.
- Both run on the reviewer setting (`QC_PROVIDER`, `QC_MODEL`), which can be a different model from the writer.
- Each layer can be rerun on its own; each report records the lesson version it checked.
