"""Ingestion orchestration: extract -> chunk -> embed -> upsert.

The chunk-record builder (`build_records`) is pure logic and unit-tested; the
async `ingest_pdf` wires it to Ollama embeddings + Pinecone.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple

from .books_catalog import BooksCatalog
from .chunking import split_text
from .embeddings import EmbeddingsClient
from .pdf import extract_pages
from .pinecone_store import PineconeStore


def build_records(
    pages: List[Tuple[int, str]],
    book_title: str,
    source_file_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """Turn extracted pages into chunk records with per-book metadata.

    Metadata is aligned to the real omni-rag-pdfs index + book_title:
    {text_content, book_title, source_file_id, page_number, chapter, chunk_index}.
    ``chunk_index`` is a running counter across the whole document.
    """
    records: List[Dict[str, Any]] = []
    chunk_index = 0
    for page_num, page_text in pages:
        for chunk in split_text(page_text, chunk_size, chunk_overlap):
            records.append(
                {
                    "id": f"{_slug(book_title)}-{source_file_id[:8]}-{chunk_index}",
                    "text": chunk,
                    "metadata": {
                        "text_content": chunk,
                        "book_title": book_title,
                        "source_file_id": source_file_id,
                        "page_number": page_num,
                        "chapter": 0,
                        "chunk_index": chunk_index,
                    },
                }
            )
            chunk_index += 1
    return records


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")[:40] or "book"


async def ingest_pdf(
    data: bytes,
    book_title: str,
    embeddings: EmbeddingsClient,
    store: PineconeStore,
    chunk_size: int,
    chunk_overlap: int,
    catalog: "BooksCatalog | None" = None,
) -> Dict[str, Any]:
    """Full pipeline. Returns a summary dict. Also upserts the books catalog so
    the book can be resolved by title at search time (plan §2A)."""
    source_file_id = uuid.uuid4().hex
    pages = extract_pages(data)
    if not pages:
        return {
            "book_title": book_title,
            "source_file_id": source_file_id,
            "pages": 0,
            "chunks": 0,
            "upserted": 0,
            "message": "No extractable text found in PDF (scanned/image-only?).",
        }

    records = build_records(pages, book_title, source_file_id, chunk_size, chunk_overlap)
    if not records:
        return {
            "book_title": book_title,
            "source_file_id": source_file_id,
            "pages": len(pages),
            "chunks": 0,
            "upserted": 0,
            "message": "PDF produced no chunks.",
        }

    texts = [r["text"] for r in records]
    vectors_values = await embeddings.embed_many(texts)

    pc_vectors = [
        {"id": r["id"], "values": v, "metadata": r["metadata"]}
        for r, v in zip(records, vectors_values)
    ]
    upserted = store.upsert(pc_vectors)

    if catalog is not None:
        try:
            await catalog.upsert(source_file_id, book_title, chunk_count=len(records))
        except Exception:  # noqa: BLE001 - catalog is best-effort
            pass

    return {
        "book_title": book_title,
        "source_file_id": source_file_id,
        "pages": len(pages),
        "chunks": len(records),
        "upserted": upserted,
        "message": f"Ingested '{book_title}': {upserted} chunks across {len(pages)} pages.",
    }
