"""Pinecone vector store wrapper — upsert + query.

Uses the official ``pinecone`` SDK (v5+). The index is expected to already
exist with a dimension matching ``EMBEDDING_DIM``; if missing we attempt to
create a serverless index.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError:  # pragma: no cover - exercised only when SDK absent
    Pinecone = None  # type: ignore
    ServerlessSpec = None  # type: ignore


class PineconeStore:
    def __init__(self, api_key: str, index_name: str, dimension: int):
        if Pinecone is None:
            raise ImportError("pinecone SDK not installed")
        self.dimension = dimension
        self.index_name = index_name
        self._pc = Pinecone(api_key=api_key)
        self._ensure_index()
        self.index = self._pc.Index(index_name)

    def _ensure_index(self) -> None:
        existing = [i["name"] for i in self._pc.list_indexes()]
        if self.index_name not in existing:
            self._pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

    def upsert(self, vectors: List[Dict[str, Any]]) -> int:
        """Upsert vectors. Each item: {id, values, metadata}. Batches of 100."""
        total = 0
        for i in range(0, len(vectors), 100):
            batch = vectors[i : i + 100]
            self.index.upsert(vectors=batch)
            total += len(batch)
        return total

    def query(
        self,
        vector: List[float],
        top_k: int,
        source_file_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Query top_k matches, optionally narrowed to a set of source_file_ids
        (book-title narrowing — the same book may have several ids). See plan §2A."""
        kwargs: Dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "include_metadata": True,
        }
        if source_file_ids:
            kwargs["filter"] = {"source_file_id": {"$in": source_file_ids}}
        result = self.index.query(**kwargs)
        matches = result.get("matches", []) if isinstance(result, dict) else result.matches
        out: List[Dict[str, Any]] = []
        for m in matches:
            md = m["metadata"] if isinstance(m, dict) else m.metadata
            score = m["score"] if isinstance(m, dict) else m.score
            md = md or {}
            # Metadata schema aligned to the real omni-rag-pdfs index.
            out.append(
                {
                    "text_content": md.get("text_content", ""),
                    "book_title": md.get("book_title", ""),
                    "source_file_id": md.get("source_file_id", ""),
                    "page_number": md.get("page_number", md.get("page", 0)),
                    "score": score,
                }
            )
        return out
