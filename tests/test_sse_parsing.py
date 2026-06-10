import json

from agent.app.tools.pdf_search import parse_sse_sources, PDF_EMPTY
from retrieval.app.search import sse_event


def test_sse_event_format():
    out = sse_event("status", {"stage": "embedding", "message": "hi"})
    assert out.startswith("event: status\n")
    assert "data: " in out
    assert out.endswith("\n\n")
    # data line is valid JSON
    data_line = out.split("data: ", 1)[1].strip()
    assert json.loads(data_line)["stage"] == "embedding"


def test_parse_sources_success():
    body = (
        'event: status\ndata: {"stage":"embedding"}\n\n'
        'event: sources\ndata: {"sources":[{"text_content":"chunk A","book_title":"B1","page":1,"score":0.9},'
        '{"text_content":"chunk B","book_title":"B1","page":2,"score":0.8}]}\n\n'
        'event: done\ndata: {}\n\n'
    )
    result = parse_sse_sources(body)
    assert result.startswith("[PDF_SUCCESS|Found 2 matching chunks]")
    assert "chunk A" in result and "chunk B" in result
    assert "\n---\n" in result


def test_parse_sources_error_event_is_empty():
    body = (
        'event: status\ndata: {"stage":"retrieval"}\n\n'
        'event: error\ndata: {"stage":"retrieval","message":"No matching documents found."}\n\n'
        'event: done\ndata: {}\n\n'
    )
    assert parse_sse_sources(body) == PDF_EMPTY


def test_parse_sources_no_sources_is_empty():
    body = 'event: status\ndata: {"stage":"embedding"}\n\nevent: done\ndata: {}\n\n'
    assert parse_sse_sources(body) == PDF_EMPTY


def test_parse_sources_crlf():
    body = (
        'event: sources\r\ndata: {"sources":[{"text_content":"x"}]}\r\n\r\n'
    )
    assert "[PDF_SUCCESS|Found 1 matching chunks]" in parse_sse_sources(body)


def test_parse_sources_tags_with_book():
    body = 'event: sources\ndata: {"sources":[{"text_content":"y","book_title":"Dune"}]}\n\n'
    out = parse_sse_sources(body)
    assert "[book: Dune] y" in out


def test_parse_clarification_event_becomes_marker():
    body = (
        'event: status\ndata: {"stage":"embedding"}\n\n'
        'event: clarification\ndata: {"book":"dune","candidates":["Dune","Dune Messiah"]}\n\n'
        'event: done\ndata: {}\n\n'
    )
    out = parse_sse_sources(body)
    assert out.startswith("[NEEDS_CLARIFICATION|")
    assert "Dune" in out and "Dune Messiah" in out
