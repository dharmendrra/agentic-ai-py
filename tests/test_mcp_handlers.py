"""Tests for MCP handlers using a lightweight in-memory fake of the motor API.

Exercises the dispatch + JSON-arg parsing + $set semantics without a real Mongo.
"""
import pytest

from mcp_server.app.handlers import Handlers, tool_definitions, _parse_json


def test_tool_definitions_parity():
    names = {t["name"] for t in tool_definitions()}
    assert names == {
        "list_collections",
        "query_documents",
        "insert_document",
        "update_document",
        "delete_document",
    }


def test_parse_json_rejects_non_object():
    with pytest.raises(ValueError):
        _parse_json("[1,2]", "filter")
    with pytest.raises(ValueError):
        _parse_json("not json", "filter")
    assert _parse_json('{"a":1}', "filter") == {"a": 1}


# ── In-memory fake motor db ────────────────────────────────────────────────
class FakeResult:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self._docs)


class FakeCollection:
    def __init__(self):
        self.docs = []
        self._id = 0

    def find(self, filt):
        matched = [d for d in self.docs if _match(d, filt)]
        return FakeCursor(matched)

    async def count_documents(self, filt):
        return len([d for d in self.docs if _match(d, filt)])

    async def insert_one(self, doc):
        self._id += 1
        doc = dict(doc, _id=self._id)
        self.docs.append(doc)
        return FakeResult(inserted_id=self._id)

    async def update_many(self, filt, update):
        sets = update["$set"]
        matched = modified = 0
        for d in self.docs:
            if _match(d, filt):
                matched += 1
                d.update(sets)
                modified += 1
        return FakeResult(matched_count=matched, modified_count=modified)

    async def delete_many(self, filt):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not _match(d, filt)]
        return FakeResult(deleted_count=before - len(self.docs))


def _match(doc, filt):
    return all(doc.get(k) == v for k, v in filt.items())


class FakeDB:
    def __init__(self):
        self._colls = {}

    def __getitem__(self, name):
        return self._colls.setdefault(name, FakeCollection())

    async def list_collection_names(self):
        return list(self._colls.keys())


@pytest.fixture
def handlers():
    return Handlers(FakeDB())


@pytest.mark.asyncio
async def test_insert_query_update_delete_cycle(handlers):
    out = await handlers.dispatch(
        "insert_document",
        {"collection": "tasks", "document": '{"Name":"Study","Status":"To Do"}'},
    )
    assert "inserted with _id" in out

    out = await handlers.dispatch(
        "query_documents", {"collection": "tasks", "filter": '{"Status":"To Do"}'}
    )
    assert "Study" in out

    out = await handlers.dispatch(
        "update_document",
        {"collection": "tasks", "filter": '{"Name":"Study"}', "update": '{"Status":"Done"}'},
    )
    assert "matched: 1, modified: 1" in out

    out = await handlers.dispatch(
        "query_documents", {"collection": "tasks", "filter": '{"Status":"To Do"}'}
    )
    assert out == "no documents found"

    out = await handlers.dispatch(
        "delete_document", {"collection": "tasks", "filter": '{"Name":"Study"}'}
    )
    assert "deleted: 1" in out


@pytest.mark.asyncio
async def test_list_collections(handlers):
    await handlers.dispatch(
        "insert_document", {"collection": "a", "document": '{"x":1}'}
    )
    out = await handlers.dispatch("list_collections", {})
    assert '"name": "a"' in out
    assert '"count": 1' in out


@pytest.mark.asyncio
async def test_required_fields(handlers):
    with pytest.raises(ValueError):
        await handlers.dispatch("query_documents", {})
    with pytest.raises(ValueError):
        await handlers.dispatch("insert_document", {"collection": "a"})
    with pytest.raises(ValueError):
        await handlers.dispatch("update_document", {"collection": "a", "filter": "{}"})


@pytest.mark.asyncio
async def test_unknown_tool(handlers):
    with pytest.raises(ValueError):
        await handlers.dispatch("nope", {})
