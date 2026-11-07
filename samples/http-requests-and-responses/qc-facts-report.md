# Fact check report: HTTP Requests and Responses

Reviewed by gemini:gemini-flash-lite-latest on 7 Nov 2026, 18:15 UTC. Checked lesson version 3.

**Accuracy: 86%.** 22 of 29 checkable claims are supported by the sources. 6 partly supported and 1 unsupported. 11 of 24 sources are not cited.

## Issues

### F1 (medium) Not supported by the sources
Section: sec-3
“In order to receive a 500 response code, your network connection must be functioning well enough to reach the server and receive the reply”

Suggestion: Support it with a source from the research, or remove it.

### F2 (low) Only partly supported
Section: sec-2
“A query parameter is a key-value pair appended after a question mark in the URL string, such as /map?city=boston” The passages support that query parameters are key-value pairs appended after a question mark in the URL, but the specific example `/map?city=boston` is not explicitly stated in the text. Evidence [S5]: “A query string can be appended to the path for additional information (usually in `key=value` format).”

Suggestion: Change it to: A query parameter is a key-value pair appended after a question mark in the URL string, such as ?name=value

### F3 (low) Only partly supported
Section: sec-2
“A request body, or payload, is the data package sent directly after the HTTP headers” The passages state that the request body contains optional data sent to the server, but do not specifically state it is sent 'directly after the HTTP headers' (though headers come before the body as per S5.p7). Evidence [S14]: “Request Headers: Additional information about the request, such as browser details or accepted content types. * Request Body: Optional data sent to the server, commonly when submitting forms.”

Suggestion: Change it to: A request body is optional data sent to the server, commonly when submitting forms.

### F4 (low) Only partly supported
Section: sec-2
“POST is also non-idempotent: sending the same POST request multiple times will execute the operation multiple times” S15.p29 states that POST is 'not necessarily idempotent' rather than strictly non-idempotent in all absolute interpretations, though S11 and S2 categorize it as not idempotent. Evidence [S11]: “The POST method is not idempotent, so sending the same POST request twice may create duplicate entries.”

Suggestion: Change it to: POST is not necessarily idempotent, so sending the same POST request multiple times may further modify the state of the server.

### F5 (low) Only partly supported
Section: sec-2
“Because GET puts parameters into the URL, sensitive parameters such as passwords or access tokens are visible on screen, saved in browser history, and recorded in server logs” The passages state that data in the URL appears in browser history and server logs, but do not explicitly mention being 'visible on screen'. Evidence [S11]: “Because GET data lives in the URL, it appears in browser history, bookmarks, and server logs.”

Suggestion: Change it to: Because GET puts parameters into the URL, sensitive parameters such as passwords or access tokens are visible in browser history and server logs.

### F6 (low) Only partly supported
Section: sec-2
“Moving data from the URL to the request body only hides it from the browser address bar and history” The passages mention that POST data stays hidden in the request body, preventing bookmarks and accidental credential leaks, but do not explicitly state it only hides data from the browser address bar and history. Evidence [S11]: “POST data stays hidden in the request body, so you can’t bookmark it, but you also won’t accidentally leak credentials.”

Suggestion: Change it to: Moving data from the request body hides it from being bookmarked or accidentally leaked.

### F7 (low) Only partly supported
Section: sec-2
“Plain HTTP sends both query strings and request bodies across the network unencrypted” The passages state that port 80 is used if the connection is unencrypted, but do not specifically mention query strings and request bodies being sent unencrypted over plain HTTP in that exact phrasing. Evidence [S15]: “In HTTP implementations, TCP/IP connections are used using well-known ports (typically port 80 if the connection is unencrypted or port 443 if the connection is encrypted, see also List of TCP and UDP port numbers).”

Suggestion: Change it to: Plain HTTP uses unencrypted connections across the network.

### F8 (low) Only supported by a low-reliability source
Section: sec-2
“The HTTP GET method requests data from a specified resource” is supported only by S10.

Suggestion: Find a primary or official source for this statement.

### F9 (low) Cited source does not contain this statement
Section: sec-2
“An HTTP method is safe if it does not change server state” cites S2, S11, but the supporting text is in S15.

Suggestion: Cite S15 instead.

### F10 (low) Cited source does not contain this statement
Section: sec-2
“A method is idempotent if making multiple identical requests has the same effect on the server as making a single request” cites S2, but the supporting text is in S15.

Suggestion: Cite S15 instead.

### F11 (low) Only supported by a low-reliability source
Section: sec-2
“GET can still send data to the server” is supported only by S11.

Suggestion: Find a primary or official source for this statement.

### F12 (low) Only supported by a low-reliability source
Section: sec-2
“It does this by attaching query parameters directly to the request URL” is supported only by S11.

Suggestion: Find a primary or official source for this statement.

### F13 (low) Only supported by a low-reliability source
Section: sec-2
“URLs have length limits that restrict GET requests to roughly 2,000 to 8,000 characters depending on the browser, and they can only transmit URL-safe text” is supported only by S11.

Suggestion: Find a primary or official source for this statement.

### F14 (low) Only supported by a low-reliability source
Section: sec-2
“Because GET requests are safe and read-only, browsers and intermediate proxies can cache them to speed up subsequent visits” is supported only by S11.

Suggestion: Find a primary or official source for this statement.

### F15 (low) Only supported by a low-reliability source
Section: sec-2
“The HTTP POST method submits data to be processed by a specified resource, such as creating a new database record or submitting an order form” is supported only by S10, S11.

Suggestion: Find a primary or official source for this statement.

### F16 (low) Only supported by a low-reliability source
Section: sec-2
“Unlike GET, POST sends its data inside the request body rather than the URL” is supported only by S11.

Suggestion: Find a primary or official source for this statement.

### F17 (low) Only supported by a low-reliability source
Section: sec-2
“POST can transmit any data format defined by the Content-Type header, including JSON, XML, or binary files, and it does not have the strict character length limits of URL query strings” is supported only by S11.

Suggestion: Find a primary or official source for this statement.

### F18 (low) Cited source does not contain this statement
Section: sec-3
“An HTTP response begins with a three-digit status code issued by the server to tell the client the result of its request” cites S10, S12, but the supporting text is in S14.

Suggestion: Cite S14 instead.

### F19 (low) Cited source does not contain this statement
Section: sec-3
“404 Not Found means the requested URL resource does not exist on the server” cites S14, but the supporting text is in S3.

Suggestion: Cite S3 instead.

## Claims

| Id | Claim | Section | Verdict | Evidence |
|---|---|---|---|---|
| C1 | HTTP methods tell the web server what kind of action the client wants to perform, while status codes provide a standardized numeric reply showing what happened | sec-1 | supported | [S23] “In the previous lecture we learned how HTTP methods such as get, post, put, patch and delete allow client to tell a server what action it want to perform.” (exact); [S23] “This is where HTTP status code become important because these are the standard numeric response that a server send back to a client.” (exact); [S24] “So HTTP status code is a three-digit number written by a server in response to a request made by a client.” (exact) |
| C2 | The HTTP GET method requests data from a specified resource | sec-2 | supported | [S10] “* GET: Requests data from a specified resource.” (exact) |
| C3 | An HTTP method is safe if it does not change server state | sec-2 | supported | [S15] “A request method is safe if a request with that method has no intended effect on the server.” (exact) |
| C4 | A method is idempotent if making multiple identical requests has the same effect on the server as making a single request | sec-2 | supported | [S15] “A request method is idempotent if multiple identical requests with that method have the same effect as a single such request.” (exact) |
| C5 | GET is both safe and idempotent | sec-2 | supported | [S2] “/ `GET` / Yes / Yes / Yes /” (exact) |
| C6 | GET can still send data to the server | sec-2 | supported | [S11] “/ GET / Retrieves data / URL (query parameters) / ❌ No / Read/fetch data /” (exact) |
| C7 | It does this by attaching query parameters directly to the request URL | sec-2 | supported | [S11] “GET requests append data to the URL as query parameters (?name=value&role=admin), while POST requests send data in the request body.” (exact) |
| C8 | A query parameter is a key-value pair appended after a question mark in the URL string, such as /map?city=boston | sec-2 | partially supported | [S5] “A query string can be appended to the path for additional information (usually in `key=value` format).” (exact); [S11] “GET requests append data to the URL as query parameters (?name=value&role=admin)” (exact) |
| C9 | URLs have length limits that restrict GET requests to roughly 2,000 to 8,000 characters depending on the browser, and they can only transmit URL-safe text | sec-2 | supported | [S11] “URL length limits restrict GET requests to roughly 2,000-8,000 characters, depending on the browser.” (exact); [S11] “GET can only transmit URL-safe text, while POST can send any data type specified by the Content-Type header, such as JSON, XML, or binary files.” (exact) |
| C10 | Because GET requests are safe and read-only, browsers and intermediate proxies can cache them to speed up subsequent visits | sec-2 | supported | [S11] “Since GET requests don’t modify data, browsers and proxies can safely cache responses to improve performance.” (exact) |
| C11 | The HTTP POST method submits data to be processed by a specified resource, such as creating a new database record or submitting an order form | sec-2 | supported | [S10] “POST: Submits data to be processed to a specified resource.” (exact); [S11] “The HTTP POST method submits data to a server to create a new resource or trigger an action.” (exact) |
| C12 | Unlike GET, POST sends its data inside the request body rather than the URL | sec-2 | supported | [S11] “GET requests append data to the URL as query parameters (?name=value&role=admin), while POST requests send data in the request body.” (exact); [S11] “Unlike GET requests, POST requests include a request body with the sent data and the ability to change the server state.” (exact) |
| C13 | A request body, or payload, is the data package sent directly after the HTTP headers | sec-2 | partially supported | [S14] “Request Headers: Additional information about the request, such as browser details or accepted content types. * Request Body: Optional data sent to the server, ” (exact) |
| C14 | POST can transmit any data format defined by the Content-Type header, including JSON, XML, or binary files, and it does not have the strict character length limits of URL query strings | sec-2 | supported | [S11] “GET can only transmit URL-safe text, while POST can send any data type specified by the Content-Type header, such as JSON, XML, or binary files.” (exact); [S11] “URL length limits restrict GET requests to roughly 2,000-8,000 characters, depending on the browser. POST has no such restriction and can handle megabytes of da” (exact) |
| C15 | POST is not safe because it alters server state | sec-2 | supported | [S2] “POST : The `POST` method submits an entity to the specified resource, often causing a change in state or side effects on the server.” (close); [S15] “In contrast, the methods POST, PUT, DELETE, CONNECT, and PATCH are not safe. They may modify the state of the server or have other effects such as sending an em” (exact) |
| C16 | POST is also non-idempotent: sending the same POST request multiple times will execute the operation multiple times | sec-2 | partially supported | [S11] “The POST method is not idempotent, so sending the same POST request twice may create duplicate entries.” (exact); [S15] “In contrast, the methods POST, CONNECT, and PATCH are not necessarily idempotent, and therefore sending an identical POST request multiple times may further mod” (exact) |
| C17 | For this reason, POST requests are not cached by default | sec-2 | supported | [S11] “POST requests typically aren’t cached because they usually trigger actions or modify resources.” (exact); [S8] “* POST requests are never cached” (exact) |
| C18 | Because GET puts parameters into the URL, sensitive parameters such as passwords or access tokens are visible on screen, saved in browser history, and recorded in server logs | sec-2 | partially supported | [S11] “Because GET data lives in the URL, it appears in browser history, bookmarks, and server logs.” (exact); [S11] “This exposes credentials in browser history, server logs, proxy logs, and referrer headers.” (exact) |
| C19 | Moving data from the URL to the request body only hides it from the browser address bar and history | sec-2 | partially supported | [S11] “POST data stays hidden in the request body, so you can’t bookmark it, but you also won’t accidentally leak credentials.” (exact) |
| C20 | Plain HTTP sends both query strings and request bodies across the network unencrypted | sec-2 | partially supported | [S15] “In HTTP implementations, TCP/IP connections are used using well-known ports (typically port 80 if the connection is unencrypted or port 443 if the connection is” (exact) |
| C21 | An HTTP response begins with a three-digit status code issued by the server to tell the client the result of its request | sec-3 | supported | [S24] “So HTTP status code is a three-digit number written by a server in response to a request made by a client.” (exact); [S14] “* HTTP Status Code: Indicates whether the request was successful.” (exact) |
| C22 | Status codes are organized into five families based on their first digit | sec-3 | supported | [S10] “These codes are divided into five categories: ### 1xx: Informational” (exact); [S23] “So as you all know that HTTP status codes are grouped into five major categories. The first digit of the code tell us the category to which the response belongs” (exact) |
| C23 | The 2xx class indicates that the client request was successfully received, understood, and accepted by the server | sec-3 | supported | [S15] “2XX successful The request was successfully received, understood, and accepted.” (exact); [S16] “A success status indicates that the action requested by the client was received, understood, and accepted.” (exact) |
| C24 | When a read operation succeeds, the server usually replies with 200 OK and supplies the requested entity in the response body | sec-3 | supported | [S16] “200 OK Standard response for successful HTTP requests. The actual response will depend on the request method used. In a GET request, the response will contain a” (exact) |
| C25 | When a request creates a new item on the server, such as a newly inserted user account, the server returns 201 Created | sec-3 | supported | [S22] “201 Created is another thumbs up, for when something new was created.” (exact); [S11] “The server responds with details about the newly created resource: 
```
HTTP/1.1 201 Created
Location: /api/users/12345
Content-Type: application/json

{
  "id"” (exact) |
| C26 | The 4xx class indicates that the request cannot be fulfilled due to a problem on the client side | sec-3 | supported | [S15] “4XX client error The request cannot be fulfilled due to an issue that the client might be able to control.” (exact) |
| C27 | 404 Not Found means the requested URL resource does not exist on the server | sec-3 | supported | [S3] “`404 Not Found` : The server cannot find the requested resource. In the browser, this means the URL is not recognized.” (exact) |
| C28 | The 5xx class indicates that the server encountered an internal failure while trying to process a request | sec-3 | supported | [S15] “5XX server error The server failed to fulfill an apparently valid request.” (exact); [S4] “The HTTP `500 Internal Server Error` server error response status code indicates that the server encountered an unexpected condition that prevented it from fulf” (exact) |
| C29 | In order to receive a 500 response code, your network connection must be functioning well enough to reach the server and receive the reply | sec-3 | unsupported | none |

## Sources

| Id | Source | Tier | Score | Cited | Flags |
|---|---|---|---|---|---|
| S1 | RFC 9110: HTTP Semantics / RFC Editor | primary | 0.97 | no | Not cited |
| S2 | HTTP request methods - HTTP / MDN | official docs | 0.90 | yes | - |
| S3 | HTTP response status codes - HTTP / MDN | official docs | 0.90 | no | Not cited |
| S4 | 500 Internal Server Error - HTTP / MDN | official docs | 0.90 | yes | - |
| S5 | HTTP messages - HTTP / MDN | official docs | 0.90 | no | Not cited |
| S6 | RFC9110 | official docs | 0.90 | no | Not cited |
| S7 | Response: status property - Web APIs / MDN | official docs | 0.90 | no | Not cited |
| S8 | CS 304 GET versus POST | academic | 0.85 | yes | - |
| S9 | Hypertext Transfer Protocol (HTTP) Status Code Registry | official docs | 0.80 | no | Not cited |
| S10 | HTTP Requests and Responses Explained | unknown | 0.50 | yes | Low reliability |
| S11 | GET vs POST: Understanding HTTP Request Methods | unknown | 0.50 | yes | Low reliability |
| S12 | HTTP Status Codes (2xx / 4xx / 5xx) — Definition / FourSight Glossary | unknown | 0.50 | yes | Low reliability |
| S13 | 📡 HTTP Request & Response Explained | community | 0.45 | yes | Low reliability |
| S14 | Understanding HTTP and Web Communication - GeeksforGeeks | community | 0.45 | yes | Low reliability |
| S15 | HTTP (Wikipedia) | reference | 0.70 | yes | - |
| S16 | List of HTTP status codes (Wikipedia) | reference | 0.70 | yes | - |
| S17 | HTTP: The Definitive Guide | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S18 | RESTful Web APIs: Services for a Changing World | publisher | 0.80 | no | Not cited, Bibliographic record only |
| S19 | Http Methods | community | 0.65 | no | Not cited |
| S20 | HTTP crash course / http Methods / http headers | community | 0.65 | no | Not cited |
| S21 | #8 Django tutorials / GET vs POST / HTTP Methods | community | 0.65 | yes | - |
| S22 | HTTP Status Codes Explained In 5 Minutes | community | 0.65 | no | Not cited |
| S23 | HTTP Status Codes Explained for REST APIs (200, 400, 404, 500) | community | 0.58 | yes | - |
| S24 | HTTP Status Codes Explained (2xx, 3xx, 4xx, 5xx) / Intro | community | 0.58 | yes | - |
