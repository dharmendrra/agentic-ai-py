# Agentic AI (Python) — Your Library Knowledge Base

A conversational **Reasoning + Acting (ReAct)** assistant in Python: ask a
question and the agent thinks step-by-step, calling tools across **your PDF
library** (vector search over Pinecone) and **live web search** (Tavily),
grounding multi-step answers in real, cited sources — with conversation memory
and a past-conversations sidebar.

Python counterpart of the Go [`agentic-ai`](https://github.com/dharmendrra/agentic-ai)
system, rebuilt from scratch on FastAPI (ingestion + retrieval + MCP server all
in Python). Showcase + screenshots: **<https://dharmendrra.github.io/agentic-ai-py/>**.

## Features

- **Source toggles** — every turn runs against your chosen sources:
  - **Web** — live search via Tavily, with **clickable citations that persist**
    across refresh.
  - **My Library** — native PDF retrieval over a Pinecone index, narrowed by a
    Mongo **books catalog** (title/aliases → `source_file_id`).
  - Both off → the model's own knowledge. Both on → results are merged.
- **Honest provenance** — every answer is labelled by where it came from
  (`from My Library` · `from Web` · `from Database` · model's own knowledge),
  on every turn, not just the first.
- **Conversation memory** — token-budgeted tiered context (rolling summary +
  last *K* verbatim turns); the agent can recall earlier questions in the thread.
- **Clarify-back** — when a book can't be pinned to a single title, the agent
  asks which one you mean instead of guessing across thousands of chunks.
- **PDF ingestion** — drag-and-drop a PDF; it's extracted → chunked → embedded →
  upserted to Pinecone and added to the books catalog (with live status).
- **Robust ReAct loop** — bounded steps; any step with no tool call is treated
  as the final answer (so weaker local models don't loop to the step limit).
- **python.org-styled UI** with Lucide icons; a built-in vector search-test panel.

## How it works

```
                      ┌──────────────┐
                      │  LLM backend │  Claude (opt) · Ollama (local)
                      └──────┬───────┘
                             │ ReAct loop (Thought → Action → Observation)
   ┌─────────────────────────┼─────────────────────────┐
   ▼                         ▼                          ▼
search_pdf               web_search                 recall_history / mcp
(Pinecone + catalog)     (Tavily)                   (conversation memory · Mongo MCP)
```

The agent assembles a per-turn tool set from the source toggles, runs the ReAct
loop, embeds queries (`nomic-embed-text`) and searches Pinecone natively,
persists conversations + citations to MongoDB, and ingests PDFs.

## Services

| Service | Port | Run |
|---|---|---|
| `agent/` — conversational ReAct agent + chat UI (FastAPI) | 8082 | `uvicorn agent.app.main:app --port 8082` |
| `retrieval/` — PDF ingest + vector search + upload UI (FastAPI + Pinecone) | 8081 | `uvicorn retrieval.app.main:app --port 8081` |
| `mcp_server/` — MongoDB MCP server (mcp SDK, SSE) | 8083 | `uvicorn mcp_server.app.server:app --port 8083` |

UIs: agent chat at <http://localhost:8082>, retrieval upload + search-test at
<http://localhost:8081>.

## Setup

### One-shot (macOS / Homebrew)

```bash
chmod +x setup.sh      # first time only
./setup.sh             # idempotent — safe to re-run
./run.sh               # launch all three services
```

`setup.sh` installs/verifies Python 3.11+, MongoDB, and Ollama; creates `.venv`
and runs `pip install -e ".[dev]"`; pulls the embedding model
(`nomic-embed-text`) and a chat model (`gemma2:2b`); copies
`config.example.json` → `config.json` if missing; and writes a `run.sh`
launcher. It is idempotent and degrades gracefully when a dependency is absent.

API keys (Tavily / Pinecone / Anthropic) can't be auto-provisioned. `setup.sh`
reads them from the environment if set, otherwise writes placeholders into
`config.json` and prints exactly which keys to fill in. Without keys, plain
Ollama chat still works; Web and My Library features are limited.

### Manual

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.json config.json   # then fill in keys
```

Config is read from `config.json` (gitignored) at the repo root, falling back to
`config.example.json`. Env vars of the same name override file values.

### LLM backend rule

Anthropic is used **only** when `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, and
`ANTHROPIC_CREDIT_BALANCE: true` are all set; otherwise Ollama (local).

## Tests

```bash
pytest -q
```

72 unit tests cover pure logic only — chunking, context budget, SSE parsing,
prompt building, the ReAct loop, `recall_history` modes, MCP handlers (in-memory
fake), ingestion records, books catalog, summary folding, LLM selection — with
no external services required.

## Repo layout

```
agent/app/        ReAct loop, prompts, context/summary, store, chat UI, tools/
retrieval/app/    PDF extract · chunking · embeddings · Pinecone · books catalog · search · upload UI
mcp_server/app/   MongoDB MCP server (tools/list · tools/call over SSE)
shared/           shared config + shared static (stylesheet)
docs/             GitHub Pages showcase + format/dataflow docs
tests/            unit tests (no external services)
```

### Docs

Format and architecture references live in `docs/`:
[`DATAFLOW.md`](docs/DATAFLOW.md) ·
[`API.md`](docs/API.md) ·
[`INGESTION_FORMAT.md`](docs/INGESTION_FORMAT.md) ·
[`PDF_ENDPOINT_SSE_FORMAT.md`](docs/PDF_ENDPOINT_SSE_FORMAT.md) ·
[`CONVERSATION_STORAGE_FORMAT.md`](docs/CONVERSATION_STORAGE_FORMAT.md) ·
[`MCP_SERVER.md`](docs/MCP_SERVER.md) ·
[`MCP_CLIENT.md`](docs/MCP_CLIENT.md) ·
[`RECALL_HISTORY_TOOL.md`](docs/RECALL_HISTORY_TOOL.md) ·
[`PLAN_CONVERSATIONAL_RETRIEVAL.md`](docs/PLAN_CONVERSATIONAL_RETRIEVAL.md) (locked plan).

## External dependencies

MongoDB · Pinecone · Ollama (chat + embeddings) · Tavily · Anthropic (optional).
