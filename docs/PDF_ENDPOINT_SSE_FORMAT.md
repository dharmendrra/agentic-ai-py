# PDF Search Endpoint — SSE Format (`POST :8081/api/search`)

The retrieval service streams Server-Sent Events. Request body:

```json
{ "query": "who is the protagonist?", "book_title": "Pride and Prejudice" }
```

`book_title` is optional; when present it scopes the Pinecone query to that book.

## Event sequence (happy path)

```
event: status
data: {"stage":"embedding","message":"Generating query embedding via Ollama…"}

event: status
data: {"stage":"retrieval","message":"Querying Pinecone for top K matches…"}

event: sources
data: {"sources":[{"text_content":"…","book_title":"Pride and Prejudice","page":12,"score":0.82}, …]}

event: done
data: {}
```

## No-match / failure

When Pinecone returns no usable matches, or embedding/query fails, an `error`
event is emitted instead of `sources`, always followed by `done`:

```
event: error
data: {"stage":"retrieval","message":"No matching documents found."}

event: done
data: {}
```

`stage` is `embedding` (Ollama failure) or `retrieval` (Pinecone failure / empty).

## Field descriptions

| Field | Type | Notes |
|---|---|---|
| `stage` | string | `embedding` \| `retrieval` |
| `message` | string | human-readable status / error |
| `sources[].text_content` | string | the chunk text (also the embedded content) |
| `sources[].book_title` | string | per-book metadata from ingestion |
| `sources[].page` | int | 1-indexed source page |
| `sources[].score` | float | cosine similarity from Pinecone |

## Edge cases

- **Empty query** → HTTP 400 (not an SSE error).
- **Pinecone not configured** (`PINECONE_API_KEY` missing) → HTTP 503 before streaming.
- **All matches empty text** → filtered out; if none remain, an `error` event is sent.

## How the agent consumes this

`agent/app/tools/pdf_search.py::parse_sse_sources` splits the body on blank lines,
collects every `sources` event's `text_content`, and returns:

- `[PDF_SUCCESS|Found N matching chunks]\n<chunk1>\n---\n<chunk2>…` on success
- `[PDF_EMPTY|No matching documents found in PDF]` when an `error` event is seen
  or no chunks were collected.

These markers (parity with the Go implementation) let the ReAct loop branch on
whether the library had an answer without parsing JSON in the prompt.
