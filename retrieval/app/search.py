"""Search: query -> embed -> (book narrowing) -> Pinecone query -> SSE events.

SSE wire format (see docs/PDF_ENDPOINT_SSE_FORMAT.md):

    event: status        data: {"stage":"embedding","message":"..."}
    event: status        data: {"stage":"retrieval","message":"..."}
    event: sources       data: {"sources":[{...}, ...]}
    event: clarification data: {"book":"...","candidates":["A","B"]}   # ambiguous book
    event: error         data: {"stage":"retrieval","message":"..."}
    event: done          data: {}

Book narrowing (plan §2A): if `book` is given and a catalog is available, resolve
it -> one distinct title filters by its source_file_id(s); multiple distinct
titles -> emit a `clarification` event for the agent to ask the user.

`sse_event` is a pure helper (unit-tested); `search_stream` is the async generator.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from .books_catalog import BooksCatalog, display_titles, group_by_title
from .embeddings import EmbeddingsClient
from .pinecone_store import PineconeStore


def sse_event(event: str, data: Dict[str, Any]) -> str:
    """Format one SSE event. Trailing blank line terminates the event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def search_stream(
    query: str,
    embeddings: EmbeddingsClient,
    store: PineconeStore,
    top_k: int,
    book: Optional[str] = None,
    catalog: Optional[BooksCatalog] = None,
) -> AsyncGenerator[str, None]:
    yield sse_event(
        "status",
        {"stage": "embedding", "message": "Generating query embedding via Ollama…"},
    )
    try:
        vector = await embeddings.embed(query)
    except Exception as exc:  # noqa: BLE001
        yield sse_event("error", {"stage": "embedding", "message": f"Embedding failed: {exc}"})
        yield sse_event("done", {})
        return

    # --- Book-title narrowing (plan §2A) ---
    source_file_ids: Optional[List[str]] = None
    if book and catalog is not None:
        try:
            hits = await catalog.resolve(book)
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            grouped = group_by_title(hits)  # {title_lower: [source_file_ids]}
            if len(grouped) == 1:
                source_file_ids = next(iter(grouped.values()))
            else:
                # Multiple distinct titles → ambiguous → clarify-back.
                yield sse_event(
                    "clarification",
                    {"book": book, "candidates": display_titles(hits)},
                )
                yield sse_event("done", {})
                return
        # 0 hits → fall through to unfiltered search.

    yield sse_event(
        "status",
        {"stage": "retrieval", "message": "Querying Pinecone for top K matches…"},
    )
    try:
        sources: List[Dict[str, Any]] = store.query(vector, top_k, source_file_ids)
    except Exception as exc:  # noqa: BLE001
        yield sse_event("error", {"stage": "retrieval", "message": f"Pinecone query failed: {exc}"})
        yield sse_event("done", {})
        return

    sources = [s for s in sources if s.get("text_content")]
    if not sources:
        yield sse_event("error", {"stage": "retrieval", "message": "No matching documents found."})
        yield sse_event("done", {})
        return

    yield sse_event("sources", {"sources": sources})
    yield sse_event("done", {})
