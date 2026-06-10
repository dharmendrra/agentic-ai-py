# Mongo MCP Server (`:8083`)

Built with the official Python **`mcp`** SDK over **SSE**. Replaces the Go
`:8083` server with tool parity.

Run:

```bash
uvicorn mcp_server.app.server:app --host 0.0.0.0 --port 8083
```

## Transport

- `GET  /sse`        — event stream (client opens this first)
- `POST /messages/`  — client→server JSON-RPC messages
- `GET  /health`     — `{"status":"ok"}`

The agent's client (`agent/app/tools/mcp_client.py`) connects to `/sse`, runs the
MCP `initialize` handshake, then `tools/list` and `tools/call`.

## Tools (parity with Go `mcp/tools/handlers.go`)

| Tool | Required params | Optional | Behaviour |
|---|---|---|---|
| `list_collections` | — | — | names + document counts |
| `query_documents` | `collection` | `filter` (JSON str), `limit` (default 20) | plain `find` |
| `insert_document` | `collection`, `document` (JSON str) | — | `insert_one` |
| `update_document` | `collection`, `filter`, `update` (JSON strs) | — | `update_many` with `$set` |
| `delete_document` | `collection`, `filter` (JSON str) | — | `delete_many` |

Filters/documents/updates are passed as **JSON strings** (mirrors the Go
string-typed params). `query_documents` returns `"no documents found"` when empty.

## Example tool result (text content)

```
[
  {
    "_id": 1,
    "Name": "Study Go",
    "Status": "Done"
  }
]
```

DB name = `MONGO_DB` (default `agentic_mcps`). No vector search here — Mongo stays
plain CRUD; vectors live in Pinecone.
