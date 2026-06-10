# Ingestion Pipeline & Pinecone Metadata (`POST :8081/api/ingest`)

Multipart upload:

```
file:       <the PDF>            (required)
book_title: "Pride and Prejudice"  (optional; defaults to filename stem)
```

## Pipeline (`retrieval/app/ingest.py`)

1. **Extract** text per page — `pdf.py` (pypdf). Pages with no extractable text
   (scanned/image-only) are skipped.
2. **Chunk** with overlap — `chunking.py` (recursive splitter; langchain if
   present, else built-in). Defaults: `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150`.
3. **Embed** each chunk — `embeddings.py` → `POST {OLLAMA_HOST}/api/embeddings`
   with `{model: EMBEDDING_MODEL, prompt: chunk}`. Dimension must match the index.
4. **Upsert** to Pinecone — `pinecone_store.py`, batches of 100.

## Pinecone vector record

```jsonc
{
  "id": "pride-and-prejudice-1a2b3c4d5e6f",   // slug(book_title)-<uuid12>
  "values": [/* EMBEDDING_DIM floats */],
  "metadata": {
    "text_content": "…the chunk text…",
    "book_title":   "Pride and Prejudice",     // powers per-book identification + clarify-back
    "page":         12,                          // 1-indexed source page
    "chunk_index":  3                            // running counter across the whole document
  }
}
```

## Response

```json
{
  "book_title": "Pride and Prejudice",
  "pages": 287,
  "chunks": 642,
  "upserted": 642,
  "message": "Ingested 'Pride and Prejudice': 642 chunks across 287 pages."
}
```

## Edge cases

- **No extractable text** → `pages:0, chunks:0, upserted:0` with an explanatory message.
- **Empty upload** → HTTP 400.
- **Pinecone not configured** → HTTP 503.
- **Index missing** → auto-created as a serverless cosine index at `EMBEDDING_DIM`.
