import json

import pytest

from retrieval.app.search import search_stream
from agent.app.tools.pdf_search import _extract_input as pdf_in
from agent.app.tools.web_search import _extract_query as web_q


def test_extract_input_plain_and_json():
    assert pdf_in("dragons") == ("dragons", "")
    assert pdf_in('{"query":"winter"}') == ("winter", "")
    assert pdf_in('{"query":"who rules","book":"Game of Thrones"}') == ("who rules", "Game of Thrones")
    assert web_q('{"query":"news"}') == "news"
    assert web_q("plain text") == "plain text"


class FakeEmbeddings:
    def __init__(self, fail=False):
        self.fail = fail

    async def embed(self, text):
        if self.fail:
            raise RuntimeError("ollama down")
        return [0.1, 0.2, 0.3]


class FakeStore:
    def __init__(self, sources):
        self.sources = sources
        self.received_ids = "UNSET"

    def query(self, vector, top_k, source_file_ids=None):
        self.received_ids = source_file_ids
        return self.sources


class FakeCatalog:
    def __init__(self, hits):
        self.hits = hits

    async def resolve(self, spoken):
        return self.hits


async def _collect(gen):
    events = []
    async for chunk in gen:
        ev = chunk.split("\n", 1)[0].replace("event: ", "")
        data = chunk.split("data: ", 1)[1].strip()
        events.append((ev, json.loads(data)))
    return events


@pytest.mark.asyncio
async def test_search_stream_success():
    store = FakeStore([{"text_content": "hi", "book_title": "B", "page_number": 1, "score": 0.9}])
    events = await _collect(search_stream("q", FakeEmbeddings(), store, top_k=3))
    kinds = [e[0] for e in events]
    assert kinds == ["status", "status", "sources", "done"]
    assert events[2][1]["sources"][0]["text_content"] == "hi"
    assert store.received_ids is None  # no book → unfiltered


@pytest.mark.asyncio
async def test_search_stream_empty_emits_error():
    store = FakeStore([])
    events = await _collect(search_stream("q", FakeEmbeddings(), store, top_k=3))
    kinds = [e[0] for e in events]
    assert "error" in kinds
    assert kinds[-1] == "done"


@pytest.mark.asyncio
async def test_search_stream_embedding_failure():
    store = FakeStore([])
    events = await _collect(search_stream("q", FakeEmbeddings(fail=True), store, top_k=3))
    assert events[0][0] == "status"
    assert any(e[0] == "error" and e[1]["stage"] == "embedding" for e in events)
    assert events[-1][0] == "done"


@pytest.mark.asyncio
async def test_search_stream_book_single_title_filters_by_ids():
    # Same title, two source_file_ids → collapse to one book → $in both ids.
    store = FakeStore([{"text_content": "throne", "book_title": "Game Of Thrones", "score": 0.9}])
    cat = FakeCatalog([
        {"_id": "id1", "title": "Game Of Thrones"},
        {"_id": "id2", "title": "game of thrones"},
    ])
    events = await _collect(
        search_stream("q", FakeEmbeddings(), store, top_k=3, book="got", catalog=cat)
    )
    kinds = [e[0] for e in events]
    assert kinds == ["status", "status", "sources", "done"]
    assert store.received_ids == ["id1", "id2"]


@pytest.mark.asyncio
async def test_search_stream_book_ambiguous_emits_clarification():
    store = FakeStore([{"text_content": "x", "score": 0.9}])
    cat = FakeCatalog([
        {"_id": "id1", "title": "Dune"},
        {"_id": "id2", "title": "Dune Messiah"},
    ])
    events = await _collect(
        search_stream("q", FakeEmbeddings(), store, top_k=3, book="dune", catalog=cat)
    )
    kinds = [e[0] for e in events]
    assert kinds == ["status", "clarification", "done"]
    cands = events[1][1]["candidates"]
    assert "Dune" in cands and "Dune Messiah" in cands
