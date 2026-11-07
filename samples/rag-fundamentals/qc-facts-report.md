# Fact check report: Retrieval-Augmented Generation (RAG) Fundamentals

Reviewed by gemini:gemini-flash-lite-latest on 7 Nov 2026, 18:13 UTC. Checked lesson version 1.

**Accuracy: 93%.** 14 of 15 checkable claims are supported by the sources. 1 unsupported. 15 of 29 sources are not cited.

## Issues

### F1 (medium) Not supported by the sources
Section: sec-1
“The domestic travel reimbursement limit is $350 per ticket, submitted via Form T-4.” The passages do not contain any information about a domestic travel reimbursement limit of $350 or Form T-4.

Suggestion: Support it with a source from the research, or remove it.

### F2 (low) Cited source does not contain this statement
Section: sec-1
“A standalone language model has no awareness of events, policy changes, or proprietary documents that appeared after its training cutoff or outside its training corpus.” cites S12, S15, but the supporting text is in S25.

Suggestion: Cite S25 instead.

### F3 (low) Only supported by a low-reliability source
Section: sec-2
“A standard RAG workflow executes in three distinct steps without modifying the underlying model.” is supported only by S8.

Suggestion: Find a primary or official source for this statement.

### F4 (low) Only supported by a low-reliability source
Section: sec-3
“Grounding is the process of anchoring a model's generated response to verified, authoritative external data.” is supported only by S14.

Suggestion: Find a primary or official source for this statement.

### F5 (low) Only supported by a low-reliability source
Section: sec-3
“By grounding responses in retrieved snippets, RAG significantly reduces hallucinations.” is supported only by S13, S14.

Suggestion: Find a primary or official source for this statement.

### F6 (low) Cited source does not contain this statement
Section: sec-3
“RAG does not completely eliminate hallucinations.” cites S9, S14, but the supporting text is in S15.

Suggestion: Cite S15 instead.

### F7 (low) Only supported by a low-reliability source
Section: sec-5
“Fine-tuning is a machine learning process where you train a base language model further on domain-specific datasets.” is supported only by S12, S8.

Suggestion: Find a primary or official source for this statement.

### F8 (low) Only supported by a low-reliability source
Section: sec-5
“This process directly alters the internal parameters (weights) of the neural network.” is supported only by S12.

Suggestion: Find a primary or official source for this statement.

### F9 (low) Only supported by a low-reliability source
Section: sec-5
“RAG does not touch model weights.” is supported only by S10.

Suggestion: Find a primary or official source for this statement.

### F10 (low) Cited source does not contain this statement
Section: sec-5
“RAG does not touch model weights.” cites S4, S8, but the supporting text is in S10.

Suggestion: Cite S10 instead.

### F11 (low) Only supported by a low-reliability source
Section: sec-5
“The model's weights remain frozen, and knowledge is supplied dynamically inside the input prompt at query time.” is supported only by S12.

Suggestion: Find a primary or official source for this statement.

## Claims

| Id | Claim | Section | Verdict | Evidence |
|---|---|---|---|---|
| C1 | The domestic travel reimbursement limit is $350 per ticket, submitted via Form T-4. | sec-1 | unsupported | none |
| C2 | A standalone language model has no awareness of events, policy changes, or proprietary documents that appeared after its training cutoff or outside its training corpus. | sec-1 | supported | [S25] “They know everything about our world up until their training cutoff date and absolutely nothing about what happened 5 minutes ago. Nor do they know anything abo” (exact) |
| C3 | When a model encounters a question about facts outside its training data, it attempts to generate fluent text based on probabilistic word associations rather than real information. | sec-1 | supported | [S13] “When a RAG-enabled model lacks information about a specific topic, it searches for real data rather than inventing details.” (exact); [S28] “It means that even though it does not have the knowledge what has happened between 1st August to 31st August any events even though we ask any question the LLM ” (exact) |
| C4 | This condition is called hallucination: generating false or misleading statements presented convincingly as true facts. | sec-1 | supported | [S16] “In the field of artificial intelligence (AI), a hallucination or artificial hallucination (also called bullshitting, confabulation, delusion, or mirage) is a re” (exact) |
| C5 | Retrieval-augmented generation (RAG) is a technique that enables large language models to retrieve and incorporate information from external data sources before generating a response. | sec-2 | supported | [S15] “Retrieval-augmented generation (RAG) is a technique that enables large language models (LLMs) to retrieve and incorporate new information from external data sou” (exact) |
| C6 | Instead of relying only on static training data, RAG connects the language model to external storage, such as a document repository or vector database. | sec-2 | supported | [S8] “Instead of relying solely on the model's pre-trained knowledge, RAG allows the model to retrieve and integrate relevant information from an external knowledge b” (exact); [S28] “Now along with this I will be having an external database and this database we basically say it as vector database.” (exact) |
| C7 | A standard RAG workflow executes in three distinct steps without modifying the underlying model. | sec-2 | supported | [S8] “RAG involves three main steps: 1. Retrieval: When a query is received, the LLM searches through an external knowledge source — such as a database or document re” (exact) |
| C8 | RAG does not update, retrain, or modify the language model's internal weights. | sec-2 | supported | [S9] “Fine tuning involves modifying an LLM’s internal weights by training it on domain-specific data, making it highly specialized. RAG, on the other hand, retrieves” (exact); [S4] “We illustrated how the retrieval index can be hot-swapped to update the model without requirin” (exact) |
| C9 | Grounding is the process of anchoring a model's generated response to verified, authoritative external data. | sec-3 | supported | [S14] “It keeps the model anchored to real data. Effective grounding requires citing specific sources and relying only on the provided context to support claims.” (exact) |
| C10 | By grounding responses in retrieved snippets, RAG significantly reduces hallucinations. | sec-3 | supported | [S14] “RAG helps reduce hallucinations by grounding responses in retrieved documents, though proper grounding and citation are essential to minimize risk.” (exact); [S13] “This makes RAG highly effective at reducing hallucinations about retrievable knowledge.” (exact) |
| C11 | RAG does not completely eliminate hallucinations. | sec-3 | supported | [S15] “Challenges RAG does not prevent hallucinations in LLMs.” (exact) |
| C12 | Fine-tuning is a machine learning process where you train a base language model further on domain-specific datasets. | sec-5 | supported | [S12] “Fine-tuning is a machine learning development process in which a pre-trained foundation model is further trained on domain-specific data to adjust its behaviour” (exact); [S8] “Fine-tuning is the process of adapting a pre-trained LLM to perform specific tasks or cater to niche domains by further training it on curated datasets.” (exact) |
| C13 | This process directly alters the internal parameters (weights) of the neural network. | sec-5 | supported | [S12] “In essence, the model's internal parameters (weights) are optimised using your labelled examples or documents, enabling it to "learn" your task or jargon.” (exact) |
| C14 | RAG does not touch model weights. | sec-5 | supported | [S10] “RAG retrieves relevant information from external databases at inference time, augmenting model responses with retrieved context.” (exact) |
| C15 | The model's weights remain frozen, and knowledge is supplied dynamically inside the input prompt at query time. | sec-5 | supported | [S12] “RAG pipelines retrieve relevant information at query time and inject it into the LLM’s prompt (input context), rather than relying solely on the model’s fixed t” (exact) |

## Sources

| Id | Source | Tier | Score | Cited | Flags |
|---|---|---|---|---|---|
| S1 | Using Vertex AI Grounding with Google Search / Google Cloud Blog | official docs | 0.90 | yes | - |
| S2 | Retrieval Augmented Generation options and architectures on AWS - AWS Prescriptive Guidance | official docs | 0.90 | no | Not cited |
| S3 | [2005.11401] Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | academic | 0.85 | no | Not cited |
| S4 | Retrieval-Augmented Generation for Knowledge-Intensive ... | academic | 0.85 | yes | - |
| S5 | raptor: recursive abstractive processing | academic | 0.85 | no | Not cited |
| S6 | Accelerate AWS Well-Architected reviews with Generative AI / Artificial Intelligence | official docs | 0.80 | no | Not cited |
| S7 | Retrieval-augmented generation - Wikipedia | reference | 0.70 | yes | - |
| S8 | RAG vs fine-tuning: when to use each (decision guide) | unknown | 0.50 | yes | Low reliability |
| S9 | RAG vs. Fine Tuning / B EYE | unknown | 0.50 | yes | Low reliability |
| S10 | Fine-tuning vs RAG / Azion | unknown | 0.50 | yes | Low reliability |
| S11 | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks / Library / François Paupier | unknown | 0.50 | no | Not cited, Low reliability |
| S12 | Full Guide to Choosing the Right AI Stack. Part 1: RAG vs. Fine-Tuning vs. Hybrid - Intersog Israel | unknown | 0.50 | yes | Low reliability |
| S13 | RAG Vs. Fine Tuning: Which One Should You Choose? | unknown | 0.50 | yes | Low reliability |
| S14 | Essential Concepts for Retrieval-Augmented Generation (RAG) : r/Rag | community | 0.45 | yes | Low reliability |
| S15 | Retrieval-augmented generation (Wikipedia) | reference | 0.70 | yes | - |
| S16 | Hallucination (artificial intelligence) (Wikipedia) | reference | 0.70 | yes | - |
| S17 | Prompt engineering (Wikipedia) | reference | 0.70 | no | Not cited |
| S18 | Model Context Protocol for LLMs | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S19 | Building Machine Learning Systems with a Feature Store | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S20 | From Transcription to Intelligence Applying Large Language Models to Healthcare Enterprise Decision Support Systems | publisher | 0.62 | no | Not cited, Bibliographic record only |
| S21 | Illustrated Guide to AI Agents | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S22 | Large Language Models Projects | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S23 | Conceptual Modeling | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S24 | What is Retrieval-Augmented Generation (RAG)? | community | 0.65 | yes | - |
| S25 | Is RAG Still Needed? Choosing the Best Approach for LLMs | community | 0.65 | no | Not cited |
| S26 | RAG Explained For Beginners | community | 0.65 | no | Not cited |
| S27 | RAG vs Fine-Tuning vs Prompt Engineering: Optimizing AI Models | community | 0.65 | yes | - |
| S28 | Introduction To Undertsanding RAG(Retrieval-Augmented Generation) | community | 0.65 | yes | - |
| S29 | RAG Explained / All about RAG - Retrieval Augmented Generation | community | 0.65 | no | Not cited |
