# `recall_history` Tool

A **read-only, conversation-scoped** tool for deep recall of earlier turns
(plan §5, §8). The backend injects the current `conv_id` and a
`ConversationStore`; the model can never target another conversation and can
never mutate anything. This is deliberately separate from the general MCP CRUD
tools (which include `delete_document`).

## Input (JSON object; plain text also accepted)

```jsonc
{ "mode": "all" }                          // every user message, in order
{ "mode": "first_n", "n": 3 }              // first N user messages (default 3)
{ "mode": "search", "query": "dragons" }   // messages whose content matches (case-insensitive)
```

Plain-text input is coerced: `"all"`/`"first_n"`/`"search"` → that mode;
any other free text → `{mode:"search", query:<text>}`.

## Output (text)

```
First 3 user messages:
[1] user: what is python
[3] user: tell me about dragons
[5] user: python decorators
```

`mode=search` without a `query` returns an error string rather than dumping all.

## Why a dedicated tool

The per-turn prompt only carries the rolling summary + last K turns verbatim
(budgeted). `recall_history` gives the model **exact** access to older messages
on demand, so prompts stay cheap while nothing is lost (full history is always
in Mongo). See `docs/DATAFLOW.md`.
