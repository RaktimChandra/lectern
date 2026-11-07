# Fact verification of the sample lessons

The task asks for the factual accuracy of the generated content to be verified. Lectern's fact check (QC 1) is automated; this file records a manual check of the exported lessons in `samples/` against primary sources, plus a review of every QC 1 finding that was not "supported".

Result key: **Accurate** (matches the source), **Simplified** (correct for a beginner, but the source is more precise), **Imprecise** (worth correcting in the next edit).

## Lesson 1: HTTP Requests and Responses (version 3)

Primary sources: [RFC 9110, HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110) (IETF, June 2022); [RFC 9112, HTTP/1.1](https://www.rfc-editor.org/rfc/rfc9112) (IETF, June 2022); [IANA HTTP Status Code Registry](https://www.iana.org/assignments/http-status-codes).

| Statement in the lesson | Section | Primary source | Result |
|---|---|---|---|
| A method is safe if it does not change server state | 2 | RFC 9110 §9.2.1: safe methods are "essentially read-only"; the client does not request or expect a state change | Simplified |
| A method is idempotent if repeating it has the same effect as one request | 2 | RFC 9110 §9.2.2 | Accurate |
| GET is safe and idempotent | 2 | RFC 9110 §9.2.1, §9.2.2 (GET, HEAD, OPTIONS, TRACE are safe; PUT, DELETE and the safe methods are idempotent) | Accurate |
| Browsers and proxies can cache GET responses | 2 | RFC 9110 §9.3.1: the response to a GET request is cacheable | Accurate |
| GET sends data as query parameters after a `?` | 2 | RFC 9110 §4.2.1 and RFC 3986 §3.4 (query component) | Accurate |
| URL limits restrict GET to roughly 2,000 to 8,000 characters depending on the browser | 2 | RFC 9110 §4.1 recommends support for URIs of at least 8,000 octets; the 2,000 figure is an old browser limit, not a standard | Simplified |
| POST asks the resource to process the enclosed data, e.g. create a record | 2 | RFC 9110 §9.3.3 | Accurate |
| POST is not safe and not idempotent; repeating it can repeat the action | 2 | RFC 9110 §9.2.1, §9.2.2 | Accurate |
| POST requests are not cached by default | 2 | RFC 9110 §9.3.3: POST responses are cacheable only with explicit freshness information and a matching Content-Location | Accurate |
| Credentials in a URL end up in history and logs | 2 | RFC 9110 §17.9 (Sensitive Information in URIs) | Accurate |
| Plain HTTP is unencrypted; use HTTPS/TLS | 2 | RFC 9110 §4.2.2 (https is secured with TLS) | Accurate |
| "An HTTP response begins with a three-digit status code" | 3 | RFC 9112 §4: the status line begins with the HTTP version, then the status code (the lesson's own traces in section 4 show this correctly) | Imprecise |
| Status codes fall into five classes by their first digit; a client understands the class even for an unknown code | 3 | RFC 9110 §15 (an unrecognised code is treated as the x00 code of its class) | Accurate |
| 2xx: request successfully received, understood and accepted | 3 | RFC 9110 §15.3 | Accurate |
| 200 OK returns the requested representation for GET | 3 | RFC 9110 §15.3.1 | Accurate |
| 201 Created for a newly created resource (with Location) | 3, 4 | RFC 9110 §15.3.2 | Accurate |
| 4xx: the client seems to have erred | 3 | RFC 9110 §15.5 | Accurate |
| 400 Bad Request for malformed or invalid requests | 3, 4 | RFC 9110 §15.5.1. Note: for well-formed JSON that fails validation (the empty-name example), many APIs use 422 Unprocessable Content (§15.5.21); 400 is still allowed | Accurate |
| 404 Not Found means the resource does not exist | 3 | RFC 9110 §15.5.5: no current representation was found, or the server will not disclose that one exists | Simplified |
| 5xx: the server erred or cannot perform the request | 3 | RFC 9110 §15.6 | Accurate |
| 500 Internal Server Error: an unexpected condition prevented the server from fulfilling the request | 3 | RFC 9110 §15.6.1 | Accurate |
| Request line holds method, path and version; a blank line separates headers from the body | 4 | RFC 9112 §2.1, §3 | Accurate |
| GET requests do not include a body | 4 | RFC 9110 §9.3.1: content in a GET request has no defined semantics and may be rejected; it is not forbidden | Simplified |

**No statement contradicts the primary sources.** One is imprecise (the status line starts with the version, not the code) and five are reasonable beginner simplifications.

QC 1 findings reviewed:

- *Partly supported* claims C8, C13, C16, C18, C19, C20: each is correct per RFC 9110 (rows above). The cited web sources supported only part of the wording, so QC 1 was right to ask for a stronger citation. **Agreed with the flag; content kept.**
- *Unsupported* C29 ("to receive a 500 your connection must work well enough to reach the server"): true by definition (a status code is part of a response the server sent), but no source says it in words. **Dismissed as a reasoning step rather than a sourced fact.**
- Source S8 states "POST requests are never cached". RFC 9110 §9.3.3 says otherwise, and the lesson's own wording ("not cached by default") is the accurate one. This shows why sources are ranked by authority rather than treated as equally reliable.
- Planted-error test (version 2): "POST requests are idempotent, so sending the same POST twice is always safe." QC 1 marked it **contradicted** with two verbatim quotes (S11, S15), which RFC 9110 §9.2.2 confirms. Version 3 restores the original text.

## Lesson 2: Retrieval-Augmented Generation (RAG) Fundamentals (version 1)

Primary sources: [Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", NeurIPS 2020](https://arxiv.org/abs/2005.11401); [Gao et al., "Retrieval-Augmented Generation for Large Language Models: A Survey", 2023](https://arxiv.org/abs/2312.10997).

| Statement in the lesson | Section | Primary source | Result |
|---|---|---|---|
| RAG retrieves relevant passages from an external store and gives them to the model alongside the query | 2 | Lewis et al. 2020 (retriever + generator over a dense document index) | Accurate |
| The pipeline is retrieval, augmentation, generation | 2 | Gao et al. 2023, "Naive RAG": indexing, retrieval, generation | Accurate |
| Documents are embedded as vectors and stored for similarity search | 2 | Lewis et al. 2020 (dense passage retrieval over a vector index) | Accurate |
| RAG at inference does not change the model's weights | 2 | Gao et al. 2023 contrasts RAG with fine-tuning, which updates parameters. (The original Lewis et al. model fine-tunes retriever and generator together, but production RAG as taught here uses a frozen model) | Simplified |
| RAG reduces but does not eliminate hallucination; retrieval and generation can each fail | 3 | Gao et al. 2023 (retrieval and generation challenges) | Accurate |
| Retrieval and generation faithfulness should be evaluated separately | 3 | Gao et al. 2023 (evaluation of retrieval quality and generation quality) | Accurate |

QC 1 findings reviewed:

- *Unsupported* C1 ("the domestic travel reimbursement limit is $350 per ticket, submitted via Form T-4"): this is the hook's invented example of a model hallucinating, so no source should support it. **Dismissed.** It is a useful reminder that the fact check cannot tell an illustrative example from a claim; a future version could let the writer mark example text as non-checkable.
