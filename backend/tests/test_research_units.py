from lectern.research import reliability
from lectern.research.passages import PassageIndex, chunk, relevance, split_sentences
from lectern.research.providers import (
    apply_youtube_details,
    best_segment,
    parse_brave,
    parse_google_books,
    parse_iso_duration,
    parse_open_library,
    parse_tavily,
    parse_wikipedia_article,
    parse_youtube_search,
)
from lectern.models import Source

from .conftest import RFC_TEXT


# --- passages -------------------------------------------------------------------


def test_chunk_keeps_every_sentence():
    text = " ".join(f"Sentence number {i} talks about HTTP." for i in range(60))
    passages = chunk(text, target_chars=300)
    joined = " ".join(passages)
    for i in range(60):
        assert f"Sentence number {i} " in joined
    assert all(len(p) < 600 for p in passages)


def test_chunk_short_and_empty():
    assert chunk("") == []
    assert chunk("Just one sentence here.") == ["Just one sentence here."]


def test_bm25_finds_relevant_passage():
    sources = [
        Source(id="S1", kind="web", title="RFC", url="https://www.rfc-editor.org/rfc/rfc9110", text=RFC_TEXT,
               reliability=reliability.assess("https://www.rfc-editor.org", "web")),
        Source(id="S2", kind="web", title="Pasta", url="https://food.example.com", text="Boil the pasta in salted water. " * 30,
               reliability=reliability.assess("https://food.example.com", "web")),
    ]
    index = PassageIndex.from_sources(sources)
    top, _ = index.search("which methods are idempotent", k=1)[0]
    assert top.source_id == "S1" and "idempotent" in top.text
    preferred = index.search("boil salted water methods", k=2, prefer_sources=["S1"])
    assert {p.source_id for p, _ in preferred} == {"S1", "S2"}


def test_relevance():
    assert relevance("HTTP GET and POST methods", ["GET", "POST", "HTTP"]) == 1.0
    assert relevance("cooking pasta", ["GET", "POST", "HTTP"]) == 0.0
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


# --- reliability -----------------------------------------------------------------


def test_reliability_tiers():
    assert reliability.assess("https://www.rfc-editor.org/rfc/rfc9110", "web").tier == "primary"
    assert reliability.assess("https://developer.mozilla.org/en-US/docs/Web/HTTP", "web").tier == "official_docs"
    assert reliability.assess("https://cs.stanford.edu/notes", "web").tier == "academic"
    assert reliability.assess("https://en.wikipedia.org/wiki/HTTP", "encyclopedia").tier == "reference"
    assert reliability.assess("https://medium.com/@x/http", "web").tier == "community"
    assert reliability.assess("https://docs.example.dev/api", "web").tier == "official_docs"
    assert reliability.assess("https://random.example.net", "web").tier == "unknown"
    assert reliability.assess("https://random.example.net", "web", authoritative_domains=["example.net"]).tier == "official_docs"


def test_reliability_books_and_videos():
    book = reliability.assess("https://books.google.com/x", "book", publisher="O'Reilly Media")
    assert book.score >= 0.8 and "not full text" in " ".join(book.reasons)
    weak = reliability.assess("https://www.youtube.com/watch?v=1", "video")
    strong = reliability.assess("https://www.youtube.com/watch?v=1", "video", view_count=2_000_000, has_transcript=True)
    assert strong.score > weak.score and strong.score <= 0.7


# --- provider parsers ---------------------------------------------------------------


def test_parse_tavily_and_brave():
    hits = parse_tavily({"results": [{"title": "RFC", "url": "https://x.org", "content": "c", "raw_content": "full"}, {"title": "no url"}]}, "q")
    assert len(hits) == 1 and hits[0].content == "full"
    brave = parse_brave({"web": {"results": [{"title": "T", "url": "https://y.org", "description": "<b>GET</b> method"}]}}, "q")
    assert brave[0].snippet == "GET method"
    assert parse_brave({}, "q") == []


def test_parse_wikipedia():
    data = {"query": {"pages": {"1": {"title": "HTTP", "fullurl": "https://en.wikipedia.org/wiki/HTTP",
                                         "extract": "Intro text.\n== Methods ==\nGET and POST.\n== References ==\nnoise"}}}}
    title, url, text = parse_wikipedia_article(data)
    assert title == "HTTP" and "noise" not in text and "GET and POST" in text
    assert parse_wikipedia_article({"query": {"pages": {"-1": {"missing": ""}}}}) is None


def test_youtube_parsing():
    hits = parse_youtube_search({"items": [{"id": {"videoId": "v1"}, "snippet": {"title": "HTTP &amp; you", "channelTitle": "C", "publishedAt": "2021-05-01T00:00:00Z"}},
                                            {"id": {}, "snippet": {}}]}, "q")
    assert len(hits) == 1 and hits[0].title == "HTTP & you" and hits[0].published_year == 2021
    apply_youtube_details(hits, {"items": [{"id": "v1", "contentDetails": {"duration": "PT8M12S"}, "statistics": {"viewCount": "1200"}}]})
    assert hits[0].duration_seconds == 492 and hits[0].view_count == 1200
    assert hits[0].url == "https://www.youtube.com/watch?v=v1"


def test_iso_duration():
    assert parse_iso_duration("PT1H2M") == 3720
    assert parse_iso_duration("PT45S") == 45
    assert parse_iso_duration("P1DT1S") == 86401
    assert parse_iso_duration("") is None


def test_best_segment():
    transcript = [(float(i * 30), 30.0, "intro chat" if i < 10 else "GET request POST request status code") for i in range(30)]
    start, end, excerpt = best_segment(transcript, ["GET", "POST", "status code"])
    assert start >= 270 and end > start and "GET" in excerpt
    assert best_segment(transcript, ["quantum"]) is None
    assert best_segment([], ["GET"]) is None


def test_book_parsers():
    gb = parse_google_books({"items": [{"volumeInfo": {"title": "HTTP", "subtitle": "The Definitive Guide", "authors": ["A"], "publisher": "O'Reilly",
                                                        "publishedDate": "2002-09", "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781565925090"}],
                                                        "infoLink": "https://books.google.com/x"}}]}, "q")
    assert gb[0].title == "HTTP: The Definitive Guide" and gb[0].year == 2002 and gb[0].isbn == "9781565925090"
    ol = parse_open_library({"docs": [{"title": "Web Protocols", "author_name": ["B"], "first_publish_year": 2010, "key": "/works/OL1W", "isbn": ["123", "9780000000001"]}]}, "q")
    assert ol[0].url == "https://openlibrary.org/works/OL1W" and ol[0].isbn == "9780000000001"
