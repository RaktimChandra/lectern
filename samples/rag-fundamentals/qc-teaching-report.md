# Teaching quality report: Retrieval-Augmented Generation (RAG) Fundamentals

Reviewed by gemini:gemini-flash-lite-latest on 7 Nov 2026, 18:13 UTC. Checked lesson version 1.

**Quality score: 87 of 100.** 4 of 4 objective parts are taught and tested. Timing fits in 3 of 8 sections. Rubric average 4.5 of 5. 7 suggestions.

## Objective coverage

| Part | Statement | Taught in | Tested by | Status |
|---|---|---|---|---|
| O1 | Explain the step-by-step workflow of a standard RAG pipeline (retrieval, augmentation, and generation). | sec-2, sec-4 | kc-1, kc-4 | covered |
| O2 | Explain how injecting retrieved context reduces hallucinations and provides source grounding in language model outputs. | sec-3, sec-4 | kc-2, kc-4 | covered |
| O3 | Distinguish between the operational mechanisms of RAG (dynamic context retrieval) and fine-tuning (weight updates via training). | sec-5, sec-6 | kc-1, kc-3 | covered |
| O4 | Identify appropriate use cases where RAG is preferred over fine-tuning based on data volatility, cost, latency, and attribution requirements. | sec-5, sec-6 | kc-3 | covered |

## Timing (45 minutes planned, about 10.1 minutes of reading)

| Section | Allotted | Reading estimate | Words | Status |
|---|---|---|---|---|
| sec-1 | 5 | 1.3 | 240 | too short |
| sec-2 | 7 | 1.4 | 251 | too short |
| sec-3 | 6 | 1.4 | 261 | too short |
| sec-4 | 6 | 2.0 | 117 | ok |
| sec-5 | 7 | 1.6 | 291 | too short |
| sec-6 | 5 | 1.5 | 269 | ok |
| sec-7 | 5 | 0.1 | 19 | ok |
| sec-8 | 4 | 0.8 | 149 | too short |

## Rubric

| Criterion | Score | Rationale |
|---|---|---|
| objective alignment | 5 of 5 | All four objectives are thoroughly taught and assessed through aligned examples, practice scenarios, and knowledge checks. |
| clarity | 4 of 5 | Concepts like prompt augmentation, grounding, and parametric memory are clearly defined, though dense readability could be slightly improved. |
| structure and flow | 4 of 5 | The lesson flows logically from motivation (hook) to workflow, mechanics, examples, architecture trade-offs, practice, and assessment. |
| examples and practice | 5 of 5 | The customer support walkthrough and architectural scenario practice are highly realistic and directly test the core concepts. |
| engagement | 4 of 5 | Interactive scenarios and built-in self-checks maintain learner engagement despite being self-paced. |
| accuracy of level | 5 of 5 | The technical depth is perfectly calibrated for introductory engineering students. |

## Strengths

- Compelling hook addressing the stale fact problem that resonates with real-world LLM limitations.
- Clear, step-by-step breakdown of the RAG pipeline with a concrete customer support example.
- Comprehensive comparison table distinguishing RAG from fine-tuning across four key dimensions.
- Practical architecture scenarios that test learners' ability to choose between RAG and fine-tuning.

## Issues

### I1 (medium) Missing Knowledge Check Body
Section: sec-7
Section 6 introduces the knowledge check heading and points to questions that appear later under the recap section, which disrupts the expected flow.

Suggestion: Move the knowledge check questions directly into section 6 so learners complete them right after the practice activity.

### I2 (low) “The Stale Fact Problem” is thin for 5 minutes
Section: sec-1
About 1.3 minutes of reading against 5 allotted.

Suggestion: Add a worked example or a short exercise, up to about 540 words, or give the time to another section.

### I3 (low) “The Three Steps of a RAG Pipeline” is thin for 7 minutes
Section: sec-2
About 1.4 minutes of reading against 7 allotted.

Suggestion: Add a worked example or a short exercise, up to about 756 words, or give the time to another section.

### I4 (low) “Grounding and Mitigating Hallucinations” is thin for 6 minutes
Section: sec-3
About 1.4 minutes of reading against 6 allotted.

Suggestion: Add a worked example or a short exercise, up to about 648 words, or give the time to another section.

### I5 (low) “RAG vs. Fine-Tuning: Weights vs. Context” is thin for 7 minutes
Section: sec-5
About 1.6 minutes of reading against 7 allotted.

Suggestion: Add a worked example or a short exercise, up to about 756 words, or give the time to another section.

### I6 (low) “Summary and Core Takeaways” is thin for 4 minutes
Section: sec-8
About 0.8 minutes of reading against 4 allotted.

Suggestion: Add a worked example or a short exercise, up to about 432 words, or give the time to another section.

### I7 (low) “Tracing a Customer Support RAG Query” is dense
Section: sec-4
Reading ease 26.4 (very dense), 1 sentences over 30 words.

Suggestion: Split long sentences and define terms as they appear.

