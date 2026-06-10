# Conversation Storage (MongoDB, written only by the agent)

DB = `MONGO_DB` (default `agentic_mcps`). The agent uses a **direct `motor`
driver** (`agent/app/store.py`) — never the MCP CRUD tool — so persistence is
deterministic and the model can never delete history.

## `conversations`

```jsonc
{
  "_id": ObjectId,
  "title": "what is python…",     // derived from the first user query (<=60 chars)
  "created_at": ISODate,
  "updated_at": ISODate,
  "summary": "rolling summary text",   // folded older turns (see RECALL + §7)
  "summary_upto_seq": 6                 // highest seq already folded into summary
}
```

## `messages`

```jsonc
{
  "_id": ObjectId,
  "conversation_id": "<conversations._id as string>",
  "seq": 7,                       // monotonic per conversation, 1-indexed
  "role": "user" | "assistant",
  "content": "final text only",   // NEVER raw tool observations
  "sources": [ ... ],             // optional, assistant only
  "created_at": ISODate
}
```

> **Critical:** `content` holds the **final answer text only**. Raw tool
> observations (Pinecone chunks, web text) are never stored and never replayed —
> the biggest context-budget win (plan §7).

## Store API (`store.py`)

`create_conversation`, `append_message`, `get_recent_messages(k)`,
`get_messages_up_to_seq`, `get_messages_after_seq`, `get_all_user_messages`,
`get_first_n_user_messages`, `search_messages`, `get_conversation`,
`update_summary`, `list_conversations`, `get_conversation_messages`,
`delete_conversation`, `count_messages`.

`seq` is computed as `last.seq + 1` (or 1) inside `append_message`.
