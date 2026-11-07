"""Test doubles: a scripted model, a fake research toolkit and a temporary store.

The fixture texts below are short excerpts in the style of RFC 9110 and MDN,
written for these tests. They let the whole pipeline run offline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lectern.config import Settings
from lectern.llm.base import LLMClient, LLMError
from lectern.research.collector import ResearchToolkit
from lectern.research.providers import BookHit, VideoHit, WebHit
from lectern.store import LessonStore

RFC_TEXT = """HTTP Semantics

The GET method requests transfer of a current selected representation for the target resource. A successful response reflects the quality of "sameness" identified by the target URI.

The POST method requests that the target resource process the representation enclosed in the request according to the resource's own specific semantics. For example, POST is used for providing a block of data, such as the fields entered into an HTML form, to a data-handling process.

Request methods are considered "safe" if their defined semantics are essentially read-only. Of the request methods defined by this specification, the GET, HEAD, OPTIONS, and TRACE methods are defined to be safe.

A request method is considered idempotent if the intended effect on the server of multiple identical requests with that method is the same as the effect for a single such request. Of the request methods defined by this specification, PUT, DELETE, and safe request methods are idempotent.

The status code of a response is a three-digit integer code that describes the result of the request. The first digit of the status code defines the class of response. The 2xx (Successful) class of status code indicates that the client's request was successfully received, understood, and accepted. The 4xx (Client Error) class of status code indicates that the client seems to have erred. The 5xx (Server Error) class of status code indicates that the server is aware that it has erred or is incapable of performing the requested method.
"""

MDN_TEXT = """HTTP request methods

HTTP defines a set of request methods to indicate the purpose of the request and what is expected if the request is successful. The GET method requests a representation of the specified resource. Requests using GET should only retrieve data and should not contain a request content. The POST method submits an entity to the specified resource, often causing a change in state or side effects on the server.

HTTP response status codes indicate whether a specific HTTP request has been successfully completed. Responses are grouped in five classes: informational responses, successful responses, redirection messages, client error responses, and server error responses. The 404 Not Found status means the server cannot find the requested resource.
"""

BLOG_TEXT = """Understanding HTTP status codes for beginners. Status codes tell you what happened to your request. A 500 error means something went wrong on the server. Client errors such as 400 and 404 mean the request itself needs to change. Many developers confuse GET and POST when building forms. """ * 3

WIKI_TEXT = """HTTP

HTTP (Hypertext Transfer Protocol) is an application layer protocol in the Internet protocol suite for distributed, collaborative, hypermedia information systems. HTTP is a request-response protocol in the client-server model. A web browser may be the client, whereas a process running on a computer hosting a website may be the server.

The status code is a three-digit integer: the first digit defines the class of response. Common request methods include GET and POST.
"""


# ---------------------------------------------------------------------------
# Scripted model
# ---------------------------------------------------------------------------


class ScriptedLLM(LLMClient):
    """Returns fixture replies keyed by task. Values may be dicts or callables(user) -> dict."""

    def __init__(self, replies: dict, *, provider: str = "scripted", model: str = "test-model"):
        super().__init__(provider=provider, model=model, timeout=1, max_retries=1)
        self.replies = dict(replies)
        self.calls: list[str] = []
        self.fail: dict[str, Exception] = {}

    async def _call(self, task, system, user, json_schema, temperature, max_tokens) -> dict:
        self.calls.append(task)
        if task in self.fail:
            raise self.fail[task]
        reply = self.replies.get(task)
        if reply is None:
            raise LLMError(f"no scripted reply for {task}", retryable=False)
        return reply(user) if callable(reply) else reply


def http_replies() -> dict:
    sections = [
        ("hook", "What happens when you press Enter", 3, ["O1"], "Open with a browser loading a page."),
        ("concept", "Requests and responses", 9, ["O1", "O2"], "Explain request and response parts."),
        ("concept", "GET and POST", 9, ["O1", "O2", "O3"], "Explain the two methods."),
        ("example", "Reading real exchanges", 8, ["O3"], "Walk through curl examples."),
        ("concept", "Status code families", 7, ["O4"], "Explain the classes."),
        ("activity", "Classify and debug", 8, ["O3", "O4"], "Scenarios to classify."),
        ("check", "Knowledge check", 4, ["O1"], "Questions."),
        ("recap", "What to remember", 2, [], "Key points."),
    ]
    bodies = [
        "You type an address and press Enter. Your browser sends a message and a server answers.",
        "An HTTP exchange has a request and a response. HTTP is a request-response protocol in the client-server model [S3].",
        "The GET method requests transfer of a current selected representation for the target resource [S1]. "
        "POST asks the server to process the data you send [S1]. GET is safe and idempotent [S1]. "
        "POST requests are idempotent [S1].",
        "```bash\ncurl -i https://example.org/items/1\n```\n\nA 404 Not Found status means the server cannot find the requested resource [S2].",
        "The first digit of the status code defines the class of response [S1]. A 2xx code means the request was "
        "successfully received, understood, and accepted [S1]. A 4xx code means the client seems to have erred [S1]. "
        "A 5xx code means the server failed [S1].",
        "1. Read each scenario.\n2. Pick the method and the status class.\n3. Check your answer against the table below.\n\n"
        "Expected result: you classify all eight scenarios.",
        "Answer the questions below.",
        "GET reads, POST submits, and the first digit of a status code tells you who has to act.",
    ]
    return {
        "analyze": {
            "atoms": [
                {"id": "x1", "statement": "Explain what a GET request does", "verb": "explain", "bloom_level": "understand", "key_terms": ["GET", "HTTP method"]},
                {"id": "x2", "statement": "Explain what a POST request does", "verb": "explain", "bloom_level": "understand", "key_terms": ["POST", "request body"]},
                {"id": "x3", "statement": "Distinguish GET from POST", "verb": "distinguish", "bloom_level": "analyze", "key_terms": ["safe", "idempotent"]},
                {"id": "x4", "statement": "Classify status codes into 2xx, 4xx and 5xx", "verb": "classify", "bloom_level": "analyze", "key_terms": ["status code", "2xx", "4xx", "5xx"]},
            ],
            "prerequisites": ["What a URL is"],
            "misconceptions": ["POST is secure because data is not in the URL", "4xx and 5xx both mean the server broke"],
            "scope_notes": "No caching or HTTP/2.",
        },
        "plan_research": {
            "web_queries": [{"query": "HTTP GET POST semantics RFC 9110", "purpose": "methods", "atom_ids": ["O1", "O2"]},
                            {"query": "HTTP status code classes", "purpose": "status", "atom_ids": ["O4"]}],
            "video_queries": ["HTTP request methods explained"],
            "book_queries": ["HTTP definitive guide"],
            "wikipedia_titles": ["HTTP"],
            "authoritative_domains": ["https://www.rfc-editor.org/", "developer.mozilla.org"],
        },
        "outline": {"sections": [
            {"kind": k, "title": t, "minutes": m, "atom_ids": a, "plan": p} for k, t, m, a, p in sections
        ]},
        "draft": {
            "summary": "You will learn how browsers and servers talk. You will be able to choose GET or POST and read status codes.",
            "sections": [{"index": i, "body_md": b, "instructor_notes": ""} for i, b in enumerate(bodies)],
            "knowledge_checks": [
                {"atom_ids": ["O1"], "question": "What does GET do?", "options": ["Retrieves a representation", "Deletes a resource", "Encrypts data"], "answer_index": 0,
                 "explanation": "GET requests transfer of a representation of the target resource; it does not delete anything.", "source_ids": ["S1"]},
                {"atom_ids": ["O4"], "question": "A 503 response is which class?", "options": ["2xx", "4xx", "5xx"], "answer_index": 2,
                 "explanation": "Codes starting with 5 are server errors: the server failed on a request that may be valid.", "source_ids": ["S1", "S99"]},
            ],
            "videos": [{"source_id": "S6", "why": "Shows real requests in the browser."}, {"source_id": "S1", "why": "not a video"}],
        },
        "extract_claims": {"claims": [
            {"section_index": 2, "text": "The GET method requests transfer of a current selected representation for the target resource", "cited_source_ids": ["S1"], "checkable": True},
            {"section_index": 2, "text": "POST requests are idempotent", "cited_source_ids": ["S1"], "checkable": True},
            {"section_index": 4, "text": "A 5xx code means the server failed", "cited_source_ids": ["S1"], "checkable": True},
            {"section_index": 3, "text": "A 404 Not Found status means the server cannot find the requested resource", "cited_source_ids": ["S2"], "checkable": True},
            {"section_index": 0, "text": "Think of it like a letter", "cited_source_ids": [], "checkable": False},
        ]},
        "judge_claims": judge,
        "fact_review": {"gaps": [{"section_index": 4, "title": "3xx not mentioned", "detail": "The lesson lists classes but skips 3xx.", "severity": "low", "suggestion": "Mention 1xx and 3xx briefly."}]},
        "instruction_review": {
            "rubric": [{"criterion": c, "score": 4, "rationale": "Solid."} for c in
                       ["objective_alignment", "clarity", "structure_and_flow", "examples_and_practice", "engagement", "accuracy_of_level"]],
            "issues": [{"section_index": 5, "category": "practice", "severity": "medium", "title": "Scenarios not listed",
                        "detail": "The activity refers to scenarios that are not shown.", "suggestion": "List the eight scenarios.",
                        "find": "Read each scenario.", "replace": "Read each of the eight scenarios listed below."}],
            "strengths": ["Clear hook"],
        },
        "rewrite_section": {"body_md": "POST is not idempotent: sending the same request twice can create two resources [S1].", "change_summary": "Corrected the POST claim."},
        "add_check": {"atom_ids": ["O2"], "question": "What does POST do?", "options": ["Asks the server to process enclosed data", "Fetches a page", "Deletes data", "Nothing"],
                      "answer_index": 0, "explanation": "POST asks the target resource to process the representation enclosed in the request.", "source_ids": ["S1"]},
    }


def judge(user: str) -> dict:
    """Answer the judge prompt claim by claim, with verbatim quotes from the fixtures."""
    out = []
    for number, claim in re.findall(r'Claim (\d+): "([^"]+)"', user):
        n = int(number)
        if claim.startswith("The GET method"):
            out.append({"claim_index": n, "verdict": "supported", "evidence": [{"source_id": "S1.p1", "quote": "The GET method requests transfer of a current selected representation for the target resource."}], "note": ""})
        elif claim.startswith("POST requests are idempotent"):
            out.append({"claim_index": n, "verdict": "contradicted", "evidence": [{"source_id": "S1", "quote": "PUT, DELETE, and safe request methods are idempotent"}],
                        "note": "POST is not listed as idempotent.", "corrected_text": "POST requests are not idempotent"})
        elif claim.startswith("A 5xx"):
            # Supported verdict with a made-up quote: must be downgraded by code.
            out.append({"claim_index": n, "verdict": "supported", "evidence": [{"source_id": "S1", "quote": "A 5xx response always means the database crashed completely."}], "note": ""})
        else:
            out.append({"claim_index": n, "verdict": "supported", "evidence": [{"source_id": "S2", "quote": "The 404 Not Found status means the server cannot find the requested resource."}], "note": ""})
    return {"judgements": out}


# ---------------------------------------------------------------------------
# Fake research
# ---------------------------------------------------------------------------


class FakeWeb:
    name = "fakeweb"

    def __init__(self, fail_queries: set[str] | None = None):
        self.fail_queries = fail_queries or set()

    async def search(self, query: str, limit: int):
        if query in self.fail_queries:
            raise RuntimeError("search service returned 503")
        return [
            WebHit(title="RFC 9110: HTTP Semantics", url="https://www.rfc-editor.org/rfc/rfc9110", snippet="HTTP semantics", content=RFC_TEXT, query=query),
            WebHit(title="HTTP request methods - MDN", url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods", snippet="GET POST methods", content=MDN_TEXT, query=query),
            WebHit(title="Status codes for beginners", url="https://someblog.example.com/http-status", snippet="status codes GET POST", content=BLOG_TEXT, query=query),
            WebHit(title="Cooking pasta", url="https://food.example.com/pasta", snippet="boil water", content="Boil water and add salt. " * 40, query=query),
        ]


class FakeWiki:
    name = "wikipedia"

    async def search_titles(self, query, limit=2):
        return ["HTTP"]

    async def article(self, title):
        return ("HTTP", "https://en.wikipedia.org/wiki/HTTP", WIKI_TEXT)


class FakeYouTube:
    name = "youtube"

    async def search(self, query, limit):
        return [VideoHit(video_id="abc123", title="HTTP methods and status codes explained", channel="Teach Channel",
                         description="GET POST status code", published_year=2023, duration_seconds=640, view_count=250000, query=query)]

    async def attach_transcript(self, hit):
        hit.transcript = [(float(i * 20), 20.0, "today we look at HTTP" if i < 5 else "the GET method and POST method and each status code class 2xx 4xx 5xx")
                          for i in range(30)]


class FakeBooks:
    name = "fakebooks"

    async def search(self, query, limit):
        return [BookHit(title="HTTP: The Definitive Guide", authors=["David Gourley", "Brian Totty"], publisher="O'Reilly Media",
                        year=2002, description="A guide to HTTP methods, status codes and the protocol.", url="https://books.example.com/http-guide",
                        isbn="9781565925090", query=query)]


async def fake_fetch(url, timeout):
    raise RuntimeError("network disabled in tests")


def make_toolkit(**overrides) -> ResearchToolkit:
    kit = ResearchToolkit(web=FakeWeb(), wikipedia=FakeWiki(), youtube=FakeYouTube(), books=[FakeBooks()], fetch=fake_fetch)
    for key, value in overrides.items():
        setattr(kit, key, value)
    return kit


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, anthropic_api_key=None, openai_api_key=None,
                    gemini_api_key=None, openrouter_api_key=None, tavily_api_key=None)


@pytest.fixture
def store(settings) -> LessonStore:
    return LessonStore(settings.db_path)


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM(http_replies())
