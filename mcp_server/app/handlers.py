"""MCP tool handlers — Mongo CRUD parity with the Go mcp/tools/handlers.go.

Tools: list_collections, query_documents, insert_document, update_document,
delete_document. Each handler returns a plain text string (wrapped as MCP
TextContent by server.py). Filters/documents/updates arrive as JSON strings to
mirror the Go server's string-typed tool params.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def tool_definitions() -> List[Dict[str, Any]]:
    """JSON-schema definitions advertised via tools/list (parity with Go)."""
    return [
        {
            "name": "list_collections",
            "description": "List all MongoDB collections with their document counts",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "query_documents",
            "description": (
                "Query documents from a collection. Filter is an optional JSON "
                'object (e.g. {"Status":"To Do"}). Returns up to `limit` documents.'
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Name of the collection to query. Call list_collections first.",
                    },
                    "filter": {
                        "type": "string",
                        "description": 'Optional JSON filter object, e.g. {"Status":"To Do"}',
                    },
                    "limit": {
                        "type": "number",
                        "description": "Max documents to return (default 20)",
                    },
                },
                "required": ["collection"],
            },
        },
        {
            "name": "insert_document",
            "description": "Insert a new document into a collection",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "document": {
                        "type": "string",
                        "description": 'JSON document to insert, e.g. {"Name":"Study Go","Status":"To Do"}',
                    },
                },
                "required": ["collection", "document"],
            },
        },
        {
            "name": "update_document",
            "description": "Update documents matching a filter in a collection",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "filter": {
                        "type": "string",
                        "description": 'JSON filter to match documents, e.g. {"Name":"Study Go"}',
                    },
                    "update": {
                        "type": "string",
                        "description": 'JSON fields to set, e.g. {"Status":"Done"}',
                    },
                },
                "required": ["collection", "filter", "update"],
            },
        },
        {
            "name": "delete_document",
            "description": "Delete documents matching a filter from a collection",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Collection name"},
                    "filter": {
                        "type": "string",
                        "description": 'JSON filter to match documents, e.g. {"Name":"Study Go"}',
                    },
                },
                "required": ["collection", "filter"],
            },
        },
    ]


class Handlers:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def dispatch(self, name: str, args: Dict[str, Any]) -> str:
        fn = {
            "list_collections": self.list_collections,
            "query_documents": self.query_documents,
            "insert_document": self.insert_document,
            "update_document": self.update_document,
            "delete_document": self.delete_document,
        }.get(name)
        if fn is None:
            raise ValueError(f"unknown tool: {name}")
        return await fn(args)

    async def list_collections(self, args: Dict[str, Any]) -> str:
        names = await self.db.list_collection_names()
        result = []
        for n in sorted(names):
            try:
                count = await self.db[n].count_documents({})
            except Exception:  # noqa: BLE001
                count = -1
            result.append({"name": n, "count": count})
        return _json(result)

    async def query_documents(self, args: Dict[str, Any]) -> str:
        coll = args.get("collection", "")
        if not coll:
            raise ValueError("collection is required")
        filter_obj = _parse_json(args.get("filter", "{}") or "{}", "filter")
        limit = int(args.get("limit", 20) or 20)
        cursor = self.db[coll].find(filter_obj).limit(limit)
        docs = await cursor.to_list(length=limit)
        if not docs:
            return "no documents found"
        return _json(docs)

    async def insert_document(self, args: Dict[str, Any]) -> str:
        coll = args.get("collection", "")
        if not coll:
            raise ValueError("collection is required")
        doc_str = args.get("document", "")
        if not doc_str:
            raise ValueError("document is required")
        doc = _parse_json(doc_str, "document")
        res = await self.db[coll].insert_one(doc)
        return f"inserted with _id: {res.inserted_id}"

    async def update_document(self, args: Dict[str, Any]) -> str:
        coll = args.get("collection", "")
        filter_str = args.get("filter", "")
        update_str = args.get("update", "")
        if not coll or not filter_str or not update_str:
            raise ValueError("collection, filter, and update are all required")
        filter_obj = _parse_json(filter_str, "filter")
        update_fields = _parse_json(update_str, "update")
        res = await self.db[coll].update_many(filter_obj, {"$set": update_fields})
        return f"matched: {res.matched_count}, modified: {res.modified_count}"

    async def delete_document(self, args: Dict[str, Any]) -> str:
        coll = args.get("collection", "")
        filter_str = args.get("filter", "")
        if not coll or not filter_str:
            raise ValueError("collection and filter are required")
        filter_obj = _parse_json(filter_str, "filter")
        res = await self.db[coll].delete_many(filter_obj)
        return f"deleted: {res.deleted_count} document(s)"


def _parse_json(s: str, field: str) -> Dict[str, Any]:
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {field} JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"{field} must be a JSON object")
    return obj
