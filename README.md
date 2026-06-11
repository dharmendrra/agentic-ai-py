# agentic-ai-py

Your Library Knowledge Base — a Python assistant (+ web search and conversations) with **Web** / **My
Library** source toggles, conversation memory, a past-conversations sidebar,
clarify-back, and token-budgeted tiered context management. Python counterpart
of the Go `agentic-ai` system.

See `PLAN_CONVERSATIONAL_RETRIEVAL.md` for the locked plan and `docs/` for
formats and dataflow.

## Services

| Service | Port | Run |
|---|---|---|
| `retrieval/` — PDF ingest + vector search (FastAPI + Pinecone) | 8081 | `uvicorn retrieval.app.main:app --port 8081` |
| `agent/` — conversational ReAct agent (FastAPI) | 8082 | `uvicorn agent.app.main:app --port 8082` |
| `mcp_server/` — Mongo MCP server (mcp SDK, SSE) | 8083 | `uvicorn mcp_server.app.server:app --port 8083` |

UIs: agent chat at <http://localhost:8082>, retrieval upload at
<http://localhost:8081> (python.org theme, Lucide icons).

## Setup

### One-shot (macOS / Homebrew)

```bash
chmod +x setup.sh      # first time only
./setup.sh             # idempotent — safe to re-run
./run.sh               # launch all three services
```

`setup.sh` installs/verifies Python 3.12+, MongoDB, and Ollama; creates `.venv`
and runs `pip install -e ".[dev]"`; pulls the embedding model
(`nomic-embed-text`) and a chat model (`gemma2:2b`); copies
`config.example.json` → `config.json` if missing; and writes a `run.sh`
launcher. It is idempotent and degrades gracefully when a dependency is absent.

API keys (Tavily / Pinecone / Anthropic) can't be auto-provisioned. `setup.sh`
reads them from the environment if set, otherwise writes placeholders into
`config.json` and prints exactly which keys to fill in. Without keys, plain
Ollama chat still works; Web and My Library features are limited.

A showcase site lives in `docs/` (GitHub Pages). Preview locally with:

```bash
python3 -m http.server -d docs 8000   # then open http://localhost:8000
```

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
`ANTHROPIC_CREDIT_BALANCE: true` are all set; otherwise Ollama.

## Tests

```bash
pytest -q
```

Unit tests cover pure logic only (chunking, context budget, SSE parsing, prompt
building, ReAct loop, recall_history modes, MCP handlers with an in-memory fake,
ingestion records, summary folding) — no external services required.

## External dependencies

MongoDB, Pinecone, Ollama (LLM + embeddings), Anthropic (optional), Tavily.
