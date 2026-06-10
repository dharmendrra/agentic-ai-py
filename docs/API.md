# API Reference

## Agent service (`:8082`)

### `POST /api/agent/query`
```jsonc
// request
{ "query": "what did I ask first?", "conversation_id": "65f…", // optional
  "use_web": false, "use_library": true }

// response
{ "answer": "You first asked …",
  "conversation_id": "65f…",
  "title": "what did I ask first?",
  "needs_clarification": false }
```
- No `conversation_id` → a new conversation is created (title from the query).
- `needs_clarification: true` when the model emitted `Clarification:` (rendered
  as a normal assistant bubble in the UI).
- Persists the user message, runs the ReAct loop, persists the assistant answer,
  then may roll older turns into the conversation summary.

### `GET /api/conversations`
Returns `[{ "_id", "title", "created_at", "updated_at" }]`, newest first (sidebar).

### `GET /api/conversations/{id}`
```jsonc
{ "id": "65f…", "title": "…", "summary": "…",
  "messages": [ { "seq":1, "role":"user", "content":"…", "sources":null }, … ] }
```

### `DELETE /api/conversations/{id}`
Deletes the conversation and its messages → `{ "deleted": true }`.

### `GET /health` → `{ "status": "ok", "service": "agent" }`

---

## Retrieval service (`:8081`)

### `POST /api/ingest` (multipart)
`file` (PDF, required), `book_title` (optional). See `INGESTION_FORMAT.md`.

### `POST /api/search` → SSE
`{ "query": "...", "book_title"?: "..." }`. See `PDF_ENDPOINT_SSE_FORMAT.md`.

### `GET /health` → `{ "status": "ok", "service": "retrieval" }`

---

## MCP server (`:8083`)

`GET /sse`, `POST /messages/`, `GET /health`. See `MCP_SERVER.md`.

---

## Toggle → tool matrix

| use_web | use_library | Tools registered |
|---|---|---|
| off | off | `recall_history` only (answer from own knowledge; suggest Web if unsure) |
| off | on  | `recall_history`, `search_pdf`, `mcp` |
| on  | off | `recall_history`, `web_search` |
| on  | on  | `recall_history`, `search_pdf`, `mcp`, `web_search` |
