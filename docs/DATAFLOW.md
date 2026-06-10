# Dataflow (end-to-end + tool gating)

## Services

```
 Browser ──HTTP──> agent (:8082) ──┬── motor ──> MongoDB (conversations, messages)
                                   │
                                   ├── httpx SSE ──> retrieval (:8081) ──> Pinecone
                                   │                         └──> Ollama /api/embeddings
                                   ├── mcp SSE ───> mcp_server (:8083) ──> MongoDB (CRUD)
                                   ├── httpx ─────> Tavily (web_search)
                                   └── httpx/SDK ─> Ollama /api/generate  OR  Anthropic
```

## A single agent turn

1. `POST /api/agent/query` arrives with `use_web` / `use_library` / `conversation_id`.
2. Look up or create the conversation; **persist the user message** (final text).
3. `react.py` builds the **per-request tool set** (gating, plan §6.5):
   - always `recall_history`
   - `use_library` → `search_pdf` + `mcp`
   - `use_web` → `web_search`
4. Build the **budgeted prompt** (plan §7): branched system prompt + rolling
   `summary` + last K turns verbatim (newest-first under `HISTORY_TOKEN_BUDGET`)
   + the current question.
5. **ReAct loop** (`MAX_STEPS`): the LLM emits `Thought/Action/Action Input`;
   the tool runs; the **observation is appended to the prompt only** (transient,
   never persisted). Exits on `Final Answer:` or `Clarification:`.
6. **Persist the assistant answer** (final text only).
7. `maybe_summarize`: if the conversation exceeds `SUMMARY_TRIGGER_TURNS`, fold
   everything older than the last K turns into `conversations.summary` and
   advance `summary_upto_seq`.

## Why observations are never stored

Tool observations (Pinecone chunks, web text) are huge. Storing/replaying them
would blow the local Ollama context window. Instead: only final text is kept;
deep recall is served exactly by `recall_history`; older turns are compressed
into the rolling summary. This is the central context-management decision.

## Library retrieval detail

`search_pdf` calls retrieval `:8081/api/search` (SSE), which embeds the query via
Ollama, queries Pinecone (`top_k`, `include_metadata`), and streams `sources`
(or `error` when empty). The agent tool collapses that stream into
`[PDF_SUCCESS|…]` / `[PDF_EMPTY|…]`. `book_title` metadata flows through so the
model can cite which book and ask clarify-back questions when ambiguous.

## Safety

- `recall_history` is read-only + conversation-scoped (backend injects conv_id).
- MCP CRUD (incl. `delete_document`) is exposed **only** when My Library is on.
- Conversation collections are written **only** by the agent's `motor` store.
