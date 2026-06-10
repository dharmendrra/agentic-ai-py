"""Books catalog (Mongo) — title/aliases <-> source_file_id.

Powers book-title narrowing + clarify-back (plan §2A / decision #6). The same
collection (`books` in MONGO_DB) is shared with the Go repo and the agent.

`group_by_title` is pure logic (unit-tested); the catalog itself wraps motor.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient


def group_by_title(books: List[Dict[str, Any]]) -> "dict[str, list[str]]":
    """Group catalog hits by canonical (lowercased) title -> list of source_file_ids.

    The same book may have several source_file_ids (re-ingested copies); those
    collapse into one entry so they don't trigger a false clarify-back.
    Preserves first-seen title casing via the returned display map is the
    caller's job; here we key by lowercase and keep ids.
    """
    grouped: "dict[str, list[str]]" = {}
    for b in books:
        title = str(b.get("title", "")).strip()
        if not title:
            continue
        key = title.lower()
        grouped.setdefault(key, [])
        bid = b.get("_id") or b.get("id")
        if bid:
            grouped[key].append(str(bid))
    return grouped


def display_titles(books: List[Dict[str, Any]]) -> List[str]:
    """Distinct display titles (first-seen casing), for clarify-back prompts."""
    seen: "dict[str, str]" = {}
    for b in books:
        title = str(b.get("title", "")).strip()
        if title and title.lower() not in seen:
            seen[title.lower()] = title
    return list(seen.values())


class BooksCatalog:
    def __init__(self, mongo_uri: str, mongo_db: str):
        self._client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=3000)
        self._coll = self._client[mongo_db]["books"]

    async def ping(self) -> None:
        await self._client.admin.command("ping")

    async def resolve(self, spoken: str) -> List[Dict[str, Any]]:
        """Find catalog entries matching a spoken title (case-insensitive substring
        on title, or exact alias). Returns raw docs (may span multiple ids/titles)."""
        spoken = (spoken or "").strip().lower()
        if not spoken:
            return []
        cur = self._coll.find(
            {
                "$or": [
                    {"title": {"$regex": re.escape(spoken), "$options": "i"}},
                    {"aliases": spoken},
                ]
            }
        )
        return [doc async for doc in cur]

    async def upsert(
        self,
        source_file_id: str,
        title: str,
        aliases: Optional[List[str]] = None,
        chunk_count: int = 0,
    ) -> None:
        if not aliases:
            aliases = [title.lower()]
        await self._coll.update_one(
            {"_id": source_file_id},
            {
                "$set": {"title": title, "aliases": aliases, "chunk_count": chunk_count},
            },
            upsert=True,
        )

    async def list_all(self) -> List[Dict[str, Any]]:
        return [doc async for doc in self._coll.find({}).sort("title", 1)]
