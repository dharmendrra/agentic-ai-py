"""Retrieval service (:8081) — PDF ingestion + vector search.

Endpoints:
  POST /api/ingest   (multipart: file=<pdf>, optional book_title)
  POST /api/search   {"query": "...", "book_title"?: "..."}  -> SSE
  GET  /             upload + search test UI
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .books_catalog import BooksCatalog
from .config import get_settings
from .embeddings import EmbeddingsClient
from .ingest import ingest_pdf
from .pinecone_store import PineconeStore
from .search import search_stream

settings = get_settings()
app = FastAPI(title="agentic-ai retrieval", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"
SHARED_STATIC = Path(__file__).resolve().parents[2] / "shared" / "static"

_embeddings = EmbeddingsClient(settings.OLLAMA_HOST, settings.EMBEDDING_MODEL)
_store: PineconeStore | None = None
# Books catalog for title narrowing (best-effort; None if Mongo unreachable).
try:
    _catalog: BooksCatalog | None = BooksCatalog(settings.MONGO_URI, settings.MONGO_DB)
except Exception:  # noqa: BLE001
    _catalog = None


def get_store() -> PineconeStore:
    """Lazily construct the Pinecone store so the app imports without a key."""
    global _store
    if _store is None:
        if not settings.PINECONE_API_KEY or settings.PINECONE_API_KEY.startswith("pc-..."):
            raise HTTPException(status_code=503, detail="PINECONE_API_KEY not configured")
        _store = PineconeStore(
            settings.PINECONE_API_KEY, settings.PINECONE_INDEX, settings.EMBEDDING_DIM
        )
    return _store


class SearchRequest(BaseModel):
    query: str
    book: str | None = None  # spoken book title to narrow to (resolved via catalog)


@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...), book_title: str | None = Form(None)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="file is required")
    title = book_title or Path(file.filename).stem
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        summary = await ingest_pdf(
            data,
            title,
            _embeddings,
            get_store(),
            settings.CHUNK_SIZE,
            settings.CHUNK_OVERLAP,
            _catalog,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ingestion failed: {exc}") from exc
    return summary


@app.post("/api/search")
async def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    try:
        store = get_store()
    except HTTPException:
        raise
    return StreamingResponse(
        search_stream(
            req.query, _embeddings, store, settings.RETRIEVAL_TOP_K, req.book, _catalog
        ),
        media_type="text/event-stream",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "retrieval"}


# Single shared assets (one stylesheet for every page — no per-page copies).
if SHARED_STATIC.exists():
    app.mount("/assets", StaticFiles(directory=str(SHARED_STATIC)), name="assets")
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
