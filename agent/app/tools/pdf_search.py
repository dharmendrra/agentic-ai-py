"""search_pdf tool — async httpx SSE client to :8081/api/search.

Parity with the Go pdf_search.go:
  - collect ``event: sources`` chunks, tagged ``[book: <title>]`` for citation
  - treat ``event: error`` as "no results"
  - translate ``event: clarification`` (ambiguous book) into a
    ``[NEEDS_CLARIFICATION|...]`` marker so the agent emits a Clarification:
  - return ``[PDF_SUCCESS|Found N matching chunks]\n<joined>`` or
    ``[PDF_EMPTY|No matching documents found in PDF]``

``parse_sse_sources`` is a pure function (unit-tested).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Tuple

import httpx

PDF_EMPTY = "[PDF_EMPTY|No matching documents found in PDF]"


def parse_sse_sources(body: str) -> str:
    """Parse an SSE body into the PDF marker string.

    Splits into events on blank lines; ``sources`` events contribute book-tagged
    chunks; an ``error`` event means empty; a ``clarification`` event becomes a
    NEEDS_CLARIFICATION marker.
    """
    chunks: List[str] = []
    found_error = False

    for block in body.replace("\r\n", "\n").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = ""
        data = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()

        if event == "clarification" and data:
            try:
                payload = json.loads(data)
                book = payload.get("book", "")
                cands = ", ".join(payload.get("candidates", []))
                return f"[NEEDS_CLARIFICATION|Multiple books match '{book}': {cands}]"
            except json.JSONDecodeError:
                continue
        if event == "error":
            found_error = True
            break
        if event == "sources" and data:
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            for src in payload.get("sources", []):
                tc = src.get("text_content")
                if not tc:
                    continue
                book = src.get("book_title") or src.get("source_file_id") or ""
                chunks.append(f"[book: {book}] {tc}" if book else tc)

    if found_error or not chunks:
        return PDF_EMPTY

    joined = "\n---\n".join(chunks)
    return f"[PDF_SUCCESS|Found {len(chunks)} matching chunks]\n{joined}"


class PDFSearchTool:
    def __init__(self, endpoint: str, max_retries: int):
        self.endpoint = endpoint
        self.max_retries = max_retries

    def name(self) -> str:
        return "search_pdf"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": "search_pdf",
            "description": (
                "Search the user's PDF book library (My Library) via semantic vector "
                "search. Returns excerpts tagged with their book so you can cite the "
                "source. If the user names a specific book, pass it in the 'book' field "
                "to narrow the search to that book."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant content in PDFs",
                    },
                    "book": {
                        "type": "string",
                        "description": "Optional book title to narrow the search to a specific book",
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, input: str) -> str:
        query, book = _extract_input(input)
        payload: Dict[str, Any] = {"query": query}
        if book:
            payload["book"] = book
        body = json.dumps(payload)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        self.endpoint,
                        content=body,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code != 200:
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(attempt + 1)
                            continue
                        return PDF_EMPTY
                    return parse_sse_sources(resp.text)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(attempt + 1)
                    continue
        raise RuntimeError(
            f"search_pdf failed after {self.max_retries} retries: {last_exc}"
        )


def _extract_input(input: str) -> Tuple[str, str]:
    """Accept a plain string (query only) or JSON {query, book?}."""
    s = input.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict) and "query" in obj:
                return str(obj["query"]), str(obj.get("book", "") or "")
        except json.JSONDecodeError:
            pass
    return s, ""
