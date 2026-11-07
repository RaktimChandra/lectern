---
title: "HTTP Requests and Responses"
objective: "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories."
duration_minutes: 45
audience: beginner
delivery: self-paced
version: 3
generated: 2026-11-07
---

# HTTP Requests and Responses

You will learn how to choose between HTTP GET and POST methods based on safety, idempotency, and data placement. You will also learn to interpret 2xx, 4xx, and 5xx response codes to quickly diagnose client mistakes and server failures.

**Learning objective:** Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.

**By the end of this lesson you will be able to:**
- Explain the purpose, characteristics, and typical use cases of the HTTP GET method, including how parameters are passed.
- Explain the purpose, characteristics, and typical use cases of the HTTP POST method, including how payload data is transmitted.
- Distinguish between GET and POST methods based on data visibility, caching, idempotency, and intended side effects.
- Explain the general meaning of HTTP status code series: 2xx (Success), 4xx (Client Error), and 5xx (Server Error).
- Distinguish whether a given scenario or status code reflects a successful operation (2xx), a client-side issue (4xx), or an internal server failure (5xx).

| Part | Section | Minutes |
|---|---|---|
| 1 | A Leaked Password and a Mystery Error | 4 |
| 2 | HTTP Methods: GET and POST | 9 |
| 3 | HTTP Status Categories: 2xx, 4xx, and 5xx | 8 |
| 4 | Tracing Real HTTP Requests and Responses | 7 |
| 5 | Hands-On Scenario Classification | 8 |
| 6 | Knowledge Check | 5 |
| 7 | Summary and Next Steps | 4 |
| | **Total** | **45** |

## 1. A Leaked Password and a Mystery Error (4 min)

Imagine you build a login form for a web application. A user enters their username and secret password, clicks "Log In", and notices their password written directly inside the address bar: `https://example.com/login?username=admin&password=secret123` [S11]. That password is now preserved in the browser history, captured inside proxy logs, and saved in server access logs [S11]. Even worse, when the server rejects the request, it returns a cryptic status code like 500, leaving the user wondering if the entire server crashed or if their network cable unplugged [S4, S23].

This exact bug happens when developers confuse basic Hypertext Transfer Protocol (HTTP) request methods and misunderstand HTTP status codes [S10, S11]. HTTP methods tell the web server what kind of action the client wants to perform, while status codes provide a standardized numeric reply showing what happened [S10, S14, S23]. By understanding how methods like GET and POST handle data, and how status code series categorize results, you can design safe APIs and troubleshoot web errors efficiently [S11, S23, S24].

## 2. HTTP Methods: GET and POST (9 min)

### The GET Method

The HTTP GET method requests data from a specified resource [S10]. You use GET for safe, read-only operations that do not modify data on the server [S11]. An HTTP method is safe if it does not change server state [S2, S11]. A method is idempotent if making multiple identical requests has the same effect on the server as making a single request [S2]. GET is both safe and idempotent [S2].

GET can still send data to the server. It does this by attaching query parameters directly to the request URL [S8, S11]. A query parameter is a key-value pair appended after a question mark in the URL string, such as `/map?city=boston` [S8]. URLs have length limits that restrict GET requests to roughly 2,000 to 8,000 characters depending on the browser, and they can only transmit URL-safe text [S11]. Because GET requests are safe and read-only, browsers and intermediate proxies can cache them to speed up subsequent visits [S2, S11].

### The POST Method

The HTTP POST method submits data to be processed by a specified resource, such as creating a new database record or submitting an order form [S10, S11, S13]. Unlike GET, POST sends its data inside the request body rather than the URL [S8, S11, S14]. A request body, or payload, is the data package sent directly after the HTTP headers [S14]. POST can transmit any data format defined by the `Content-Type` header, including JSON, XML, or binary files, and it does not have the strict character length limits of URL query strings [S11].

POST is not safe because it alters server state [S2, S11]. POST is also non-idempotent: sending the same POST request multiple times will execute the operation multiple times, such as charging a payment card twice or creating duplicate database entries [S2, S11]. For this reason, POST requests are not cached by default [S2, S11].

### Comparing Data Visibility and Security

Because GET puts parameters into the URL, sensitive parameters such as passwords or access tokens are visible on screen, saved in browser history, and recorded in server logs [S11]. You should never pass sensitive credentials via GET query parameters [S11].

However, you must avoid a common security misconception: using POST does not automatically make your data secure [S11]. Moving data from the URL to the request body only hides it from the browser address bar and history [S8, S11]. Plain HTTP sends both query strings and request bodies across the network unencrypted [S10, S11]. To secure credentials against eavesdropping on the network, you must encrypt the connection using Transport Layer Security (HTTPS/TLS) alongside POST [S11].

## 3. HTTP Status Categories: 2xx, 4xx, and 5xx (8 min)

### Structure of HTTP Status Codes

An HTTP response begins with a three-digit status code issued by the server to tell the client the result of its request [S10, S12]. Status codes are organized into five families based on their first digit [S10, S12, S15]. A client interprets the broad category from the leading digit even if it does not recognize the exact code [S15].

### 2xx: Success

The 2xx class indicates that the client request was successfully received, understood, and accepted by the server [S14, S15, S16]. When a read operation succeeds, the server usually replies with `200 OK` and supplies the requested entity in the response body [S14, S16]. When a request creates a new item on the server, such as a newly inserted user account, the server returns `201 Created` [S11, S16].

### 4xx: Client Error

The 4xx class indicates that the request cannot be fulfilled due to a problem on the client side [S14, S15]. These errors are not server crashes; rather, the client provided bad, unauthorized, or malformed instructions that the server refused or could not find [S12, S14, S15]. For instance, `404 Not Found` means the requested URL resource does not exist on the server [S14]. Another common example is `400 Bad Request`, indicating that the client's request contained invalid syntax or missing required parameters [S12, S23].

### 5xx: Server Error

The 5xx class indicates that the server encountered an internal failure while trying to process a request [S14, S15]. The request syntax and headers from the client might be valid, but an issue occurred inside the server itself [S14, S15, S23].

A common misunderstanding is that a `500 Internal Server Error` means the client's network connection or physical wiring is broken [S4, S12]. That is incorrect. In order to receive a 500 response code, your network connection must be functioning well enough to reach the server and receive the reply [S10, S14]. The code `500 Internal Server Error` is a catch-all server response showing that the web server ran into an unexpected condition or unhandled software exception that prevented it from completing the job [S4].

## 4. Tracing Real HTTP Requests and Responses (7 min)

Let us trace real HTTP network transactions line by line to see methods and response codes in action [S10, S14].

### Exchange 1: Fetching a Resource with GET

A client wants to retrieve account details for user ID 42 [S10, S11].

```http
GET /users/42 HTTP/1.1
Host: api.example.com
Accept: application/json
```

The first line contains the HTTP method (`GET`), the path (`/users/42`), and the protocol version (`HTTP/1.1`) [S14]. Headers follow on separate lines [S14]. Notice that there is no request body, because GET requests do not include an entity body [S11, S14].

The server finds the record and replies:

```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 48

{
  "id": 42,
  "name": "Alice",
  "role": "Engineer"
}
```

The status line gives the protocol version and the `200 OK` status, confirming a successful fetch [S13, S16]. The response body delivers the requested JSON data [S14, S16].

### Exchange 2: Creating a Resource with POST

The client creates a new user record by sending data [S10, S11].

```http
POST /users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Length: 32

{
  "name": "Bob",
  "role": "DevOps"
}
```

Here, the method is `POST` [S11, S14]. The data appears in the request body after a blank line separating headers from payload [S11, S14]. The `Content-Type` header informs the server that the body contains JSON [S11, S14].

The server creates the account and sends back:

```http
HTTP/1.1 201 Created
Location: /users/43
Content-Length: 0
```

The `201 Created` status code confirms that the server successfully stored the new resource [S11, S16].

### Exchange 3: Client Error on Malformed POST

Now consider what happens if the client sends a malformed POST request missing required data [S12, S15]:

```http
POST /users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Length: 12

{"name": ""}
```

The server evaluates the payload, determines that user names cannot be empty strings, and rejects the submission [S14, S15]:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": "Name field cannot be blank."
}
```

The status code is in the 4xx range (`400 Bad Request`) because the failure was caused by the client sending invalid data, not by a crash in the server software [S12, S14, S15].

## 5. Hands-On Scenario Classification (8 min)

### Instructions
For each scenario below, decide:
1. The appropriate HTTP method (`GET` or `POST`) [S11].
2. The expected response category (`2xx`, `4xx`, or `5xx`) [S12, S14].

Write your answers down on paper or in a text file before checking the answers below [S11, S12].

---

#### Scenarios

1. **Filtering an Article Archive:** A user searches for articles containing the query `tag=networking` and expects a list of matching blog posts [S8, S11]. The operation reads data without modifying server state [S11].
2. **Publishing a Comment:** A reader fills in a form to publish a new comment on a forum post [S8, S11, S13]. The server receives the text and adds it to the database [S11, S16].
3. **Requesting a Missing Webpage:** A browser requests `/portfolio/2020.html` via GET, but that path does not exist on the server [S14].
4. **Database Crash During Submission:** A user submits an account registration form using POST [S11]. While processing the request, the server's backend database crashes with an unhandled exception [S4, S14].

---

### Self-Check Solutions

1. **Method:** `GET`. **Category:** `2xx` (specifically `200 OK`) [S11, S16].
   - *Explanation:* The action is a read-only search with no side effects on the server, so it should use GET with query parameters, yielding a successful 2xx response [S11, S16].
2. **Method:** `POST`. **Category:** `2xx` (specifically `201 Created`) [S11, S16].
   - *Explanation:* Publishing a comment creates new data on the server, requiring a non-idempotent POST request [S2, S11]. A successful creation returns a 2xx status code [S11, S16].
3. **Method:** `GET`. **Category:** `4xx` (specifically `404 Not Found`) [S11, S14].
   - *Explanation:* The client requested a URL that does not exist [S14]. Because the mistake comes from the client asking for an invalid resource, the server responds with a 4xx client error [S14, S15].
4. **Method:** `POST`. **Category:** `5xx` (specifically `500 Internal Server Error`) [S4, S11].
   - *Explanation:* Form submissions use POST [S11, S13]. Because an unexpected backend crash prevented the server from completing the request, the server issues a 5xx status code [S4, S14]. The network connection itself is working [S10, S14].

## 6. Knowledge Check (5 min)

Complete the following multiple-choice questions to test your understanding of HTTP methods, data transmission, and status code categories. Review your answers against the provided explanations.

**Question 1.** Which statement correctly describes how an HTTP GET request passes parameters and handles server state?

- A. GET cannot send parameters to the server because it lacks a body.
- B. GET sends parameters in the request body and modifies server records.
- C. GET sends parameters as query strings in the request URL and is a safe, idempotent method.
- D. GET sends parameters in the URL and causes permanent side effects on the database.

**Question 2.** Why is an HTTP POST request considered non-idempotent?

- A. Sending identical POST requests repeatedly may execute actions or create resources multiple times.
- B. POST requests place form data in the URL query string where it cannot be cached.
- C. POST requests only read data from the server without modifying state.
- D. POST requests are always encrypted by default, preventing repeat submissions.

**Question 3.** An engineer switches a login form from GET to POST over plain HTTP (without TLS). Why is this form still insecure against network eavesdropping?

- A. POST cannot transmit text strings, only binary data.
- B. POST automatically saves the password into the browser history.
- C. POST is only safe if placed in a query parameter.
- D. POST transmits the request body in unencrypted plaintext unless HTTPS/TLS is used.

**Question 4.** A user tries to access a webpage and receives a 404 status code. What does this code indicate?

- A. The client issued a request for a resource that could not be found on the server.
- B. The server successfully processed the request and created a new file.
- C. The user's Wi-Fi or physical network connection failed.
- D. The server software crashed due to an unhandled exception.

**Question 5.** A web client receives a `500 Internal Server Error` response from an API. What is the actual cause of this response?

- A. The network cable was unplugged, preventing any packet transmission.
- B. The client submitted bad query syntax that the client itself must reformat.
- C. The server received the request but experienced an unexpected internal condition or failure while processing it.
- D. The client requested a safe GET resource that was cached successfully.

## 7. Summary and Next Steps (4 min)

### Quick Reference

| Property / Concept | GET | POST |
| :--- | :--- | :--- |
| **Primary Purpose** | Read / retrieve data [S11] | Submit / create data [S11] |
| **Data Location** | URL query parameters [S8, S11] | Request body (payload) [S8, S11] |
| **Safe Method?** | Yes (no server state change) [S2, S11] | No (modifies resources) [S2, S11] |
| **Idempotent?** | Yes [S2] | No [S2] |
| **Default Caching** | Cacheable [S2, S11] | Not cached [S2, S11] |

| Status Family | Name | Meaning | Common Examples |
| :--- | :--- | :--- | :--- |
| **2xx** | Success | Request was received, understood, and accepted [S15] | `200 OK`, `201 Created` [S14, S16] |
| **4xx** | Client Error | Problem caused by the client's request [S14, S15] | `400 Bad Request`, `404 Not Found` [S14, S23] |
| **5xx** | Server Error | Server failed to fulfill an otherwise valid request [S4, S14] | `500 Internal Server Error` [S4, S14] |

### Next Steps
Now that you know how GET and POST work and how status codes categorize outcomes, you can inspect network traffic using browser developer tools or API clients like Postman [S11]. As you build APIs, practice selecting the correct method and returning precise status codes so clients can properly handle your server's responses [S11, S23].

## Watch next

Optional, outside the 45 minutes.

- [#8 Django tutorials | GET vs POST | HTTP Methods](https://www.youtube.com/watch?v=QD4GlXtf-WU) (Telusko, 6:07). Watch 0:04 to 5:08. It contrasts GET and POST methods and clearly shows how parameters move through URLs versus request payloads. [S21]
- [HTTP Status Codes Explained for REST APIs (200, 400, 404, 500)](https://www.youtube.com/watch?v=x2d59rJ7vgo) (Topictrick, 13:56). Watch 0:00 to 5:01. It explains the core HTTP status code categories including 200, 400, 404, and 500 when working with APIs. [S23]

## Answer key

1. **C**. GET sends data by appending query parameters to the URL string. It is defined as a safe and idempotent method because it retrieves data without altering server state. The misconception that GET cannot transmit data overlooks URL query strings.
2. **A**. POST is non-idempotent because repeating the exact same request multiple times can trigger multiple side effects, such as generating duplicate orders or records. POST is neither safe nor idempotent.
3. **D**. Moving data to a POST request body prevents it from appearing in the URL or browser history, but over unencrypted HTTP, the body is still transmitted across the network in clear text. Security against network snooping requires encryption via HTTPS/TLS.
4. **A**. 4xx codes indicate client-side errors, such as requesting a URL path that does not exist (404 Not Found). It is not a server software crash (which would yield a 5xx code) nor a local network disconnect.
5. **C**. A 500 status code indicates that the server encountered an unexpected condition that prevented it from fulfilling the request, such as an unhandled server-side crash. Since the client received this response, the network connection was working.

## References

[S2] developer.mozilla.org. HTTP request methods - HTTP | MDN. https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods (retrieved 7 Nov 2026)  
[S4] developer.mozilla.org. 500 Internal Server Error - HTTP | MDN. https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/500 (retrieved 7 Nov 2026)  
[S8] cs.wellesley.edu. CS 304 GET versus POST. https://cs.wellesley.edu/~cs304node/readings/get-versus-post (retrieved 7 Nov 2026)  
[S10] codefinity.com. HTTP Requests and Responses Explained. https://codefinity.com/blog/HTTP-Requests-and-Responses-Explained (retrieved 7 Nov 2026)  
[S11] blog.postman.com. GET vs POST: Understanding HTTP Request Methods. https://blog.postman.com/get-vs-post (retrieved 7 Nov 2026)  
[S12] foursight.cloud. HTTP Status Codes (2xx / 4xx / 5xx) — Definition | FourSight Glossary. https://foursight.cloud/glossary/http-status-codes (retrieved 7 Nov 2026)  
[S13] medium.com. 📡 HTTP Request & Response Explained. https://medium.com/@nikhilpatidar01/http-request-response-explained-cc7c30993967 (retrieved 7 Nov 2026)  
[S14] geeksforgeeks.org. Understanding HTTP and Web Communication - GeeksforGeeks. https://www.geeksforgeeks.org/blogs/http-full-form (retrieved 7 Nov 2026)  
[S15] HTTP (Wikipedia). https://en.wikipedia.org/wiki/HTTP (retrieved 7 Nov 2026)  
[S16] List of HTTP status codes (Wikipedia). https://en.wikipedia.org/wiki/List_of_HTTP_status_codes (retrieved 7 Nov 2026)  
[S21] Video: “#8 Django tutorials | GET vs POST | HTTP Methods” (Telusko, 2019, 6:07). Most relevant part: 0:04 to 5:08. https://www.youtube.com/watch?v=QD4GlXtf-WU  
[S23] Video: “HTTP Status Codes Explained for REST APIs (200, 400, 404, 500)” (Topictrick, 2026, 13:56). Most relevant part: 0:00 to 5:01. https://www.youtube.com/watch?v=x2d59rJ7vgo  
[S24] Video: “HTTP Status Codes Explained (2xx, 3xx, 4xx, 5xx) | Intro” (&BEYOND, 2026, 4:39). Most relevant part: 0:00 to 4:40. https://www.youtube.com/watch?v=JkgWhRdxg6k  
