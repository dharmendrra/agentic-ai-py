"""MongoDB conversation store (motor) — written ONLY by the agent.

Collections (DB = MONGO_DB):
  conversations: {_id, title, created_at, updated_at, summary, summary_upto_seq}
  messages:      {_id, conversation_id, seq, role, content, sources?, created_at}

`content` holds final text only — raw tool observations are never persisted.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationStore:
    def __init__(self, uri: str, db_name: str):
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self.db: AsyncIOMotorDatabase = self.client[db_name]
        self.conversations = self.db["conversations"]
        self.messages = self.db["messages"]

    def close(self) -> None:
        self.client.close()

    # ── conversations ──────────────────────────────────────────────────────
    async def create_conversation(self, title: str) -> str:
        now = _now()
        # String UUID _id (parity with the Go store) so both apps interoperate
        # on the shared conversations collection.
        cid = str(uuid.uuid4())
        doc = {
            "_id": cid,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "summary": "",
            "summary_upto_seq": 0,
        }
        await self.conversations.insert_one(doc)
        return cid

    async def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        return await self.conversations.find_one({"_id": conv_id})

    async def update_summary(self, conv_id: str, summary: str, upto_seq: int) -> None:
        await self.conversations.update_one(
            {"_id": conv_id},
            {"$set": {"summary": summary, "summary_upto_seq": upto_seq, "updated_at": _now()}},
        )

    async def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.conversations.find().sort("updated_at", -1).limit(limit)
        out = []
        async for c in cursor:
            out.append(
                {
                    "_id": str(c["_id"]),
                    "title": c.get("title", "Untitled"),
                    "created_at": c.get("created_at"),
                    "updated_at": c.get("updated_at"),
                }
            )
        return out

    async def delete_conversation(self, conv_id: str) -> bool:
        await self.messages.delete_many({"conversation_id": conv_id})
        res = await self.conversations.delete_one({"_id": conv_id})
        return res.deleted_count > 0

    # ── messages ───────────────────────────────────────────────────────────
    async def _next_seq(self, conv_id: str) -> int:
        last = await self.messages.find_one(
            {"conversation_id": conv_id}, sort=[("seq", -1)]
        )
        return (last["seq"] + 1) if last else 1

    async def append_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        sources: Optional[List[Any]] = None,
        citations: Optional[List[Any]] = None,
    ) -> int:
        seq = await self._next_seq(conv_id)
        doc = {
            "conversation_id": conv_id,
            "seq": seq,
            "role": role,
            "content": content,
            "created_at": _now(),
        }
        if sources:
            doc["sources"] = sources
        if citations:
            doc["citations"] = citations
        await self.messages.insert_one(doc)
        await self.conversations.update_one(
            {"_id": conv_id}, {"$set": {"updated_at": _now()}}
        )
        return seq

    async def get_recent_messages(self, conv_id: str, k: int) -> List[Dict[str, Any]]:
        """Last k messages, returned in chronological (ascending seq) order."""
        cursor = self.messages.find({"conversation_id": conv_id}).sort("seq", -1).limit(k)
        docs = await cursor.to_list(length=k)
        return list(reversed(docs))

    async def get_messages_up_to_seq(self, conv_id: str, seq: int) -> List[Dict[str, Any]]:
        cursor = self.messages.find(
            {"conversation_id": conv_id, "seq": {"$lte": seq}}
        ).sort("seq", 1)
        return await cursor.to_list(length=None)

    async def get_messages_after_seq(self, conv_id: str, seq: int) -> List[Dict[str, Any]]:
        cursor = self.messages.find(
            {"conversation_id": conv_id, "seq": {"$gt": seq}}
        ).sort("seq", 1)
        return await cursor.to_list(length=None)

    async def get_all_user_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        cursor = self.messages.find(
            {"conversation_id": conv_id, "role": "user"}
        ).sort("seq", 1)
        return await cursor.to_list(length=None)

    async def get_first_n_user_messages(self, conv_id: str, n: int) -> List[Dict[str, Any]]:
        cursor = self.messages.find(
            {"conversation_id": conv_id, "role": "user"}
        ).sort("seq", 1).limit(n)
        return await cursor.to_list(length=n)

    async def search_messages(self, conv_id: str, term: str) -> List[Dict[str, Any]]:
        cursor = self.messages.find(
            {
                "conversation_id": conv_id,
                "content": {"$regex": term, "$options": "i"},
            }
        ).sort("seq", 1)
        return await cursor.to_list(length=None)

    async def get_conversation_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        cursor = self.messages.find({"conversation_id": conv_id}).sort("seq", 1)
        return await cursor.to_list(length=None)

    async def count_messages(self, conv_id: str) -> int:
        return await self.messages.count_documents({"conversation_id": conv_id})
