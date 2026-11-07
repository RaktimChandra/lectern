# Fact verification of the sample lessons

The task asks for the factual accuracy of the generated content to be verified. Lectern's fact check is automated; this file records my own check of the final exported lessons against primary sources.

How to fill this in: open the exported `lesson.md`, list every factual statement, find it in the primary source, and record the result. Mark anything the lesson states that the source does not.

## Lesson 1: HTTP Requests and Responses (version __)

Primary sources: RFC 9110, HTTP Semantics (IETF, June 2022), https://www.rfc-editor.org/rfc/rfc9110 ; RFC 9112, HTTP/1.1 message syntax, https://www.rfc-editor.org/rfc/rfc9112

| Statement in the lesson | Section | Primary source and location | Result |
|---|---|---|---|
| GET requests transfer of a current selected representation of the target resource | | RFC 9110, 9.3.1 | |
| POST asks the target resource to process the enclosed representation according to its own semantics | | RFC 9110, 9.3.3 | |
| GET is safe (read-only semantics) | | RFC 9110, 9.2.1 | |
| GET is idempotent; POST is not | | RFC 9110, 9.2.2 | |
| The first digit of a status code defines its class | | RFC 9110, 15 | |
| 2xx: request successfully received, understood and accepted | | RFC 9110, 15.3 | |
| 4xx: the client seems to have erred | | RFC 9110, 15.5 | |
| 5xx: the server is aware it has erred or cannot perform the method | | RFC 9110, 15.6 | |
| 201 Created and the Location header | | RFC 9110, 15.3.2 | |
| 404 Not Found | | RFC 9110, 15.5.5 | |
| Request line, header fields and body | | RFC 9112, 2 and 3 | |
| (add every other factual statement the lesson makes) | | | |

QC Layer 1 findings I agreed with and fixed: __
QC Layer 1 findings I dismissed, and why: __

## Lesson 2: __ (version __)

Primary sources: __

| Statement in the lesson | Section | Primary source and location | Result |
|---|---|---|---|
| | | | |

QC Layer 1 findings I agreed with and fixed: __
QC Layer 1 findings I dismissed, and why: __
