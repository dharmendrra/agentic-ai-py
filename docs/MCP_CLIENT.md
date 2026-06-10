# MCP Client (in the agent)

`agent/app/tools/mcp_client.py` holds **one long-lived** MCP `ClientSession` to
the Mongo MCP server (`:8083`). Because the SSE transport and session are async
context managers, the client opens them inside a background task and keeps them
alive for the process lifetime (`connect()` waits until `initialize` completes;
`close()` signals teardown).

## The `mcp` agent tool (`mcp_tool.py`)

The LLM sees a single tool named **`mcp`**. Input is JSON with an `action` field:

```jsonc
{ "action": "list_tools" }                                 // discover operations
{ "action": "query_documents", "collection": "tasks",
  "filter": "{\"Status\":\"To Do\"}", "limit": 10 }        // call an operation
```

Everything except `action` is forwarded as the tool's arguments.

- `list_tools` → formatted listing of server tools + their required params
  (rendered via `format_input_schema`, e.g. `*collection(string), filter(string)`).
- any other action → `session.call_tool(action, params)`, returns the joined
  text content; tool errors come back as `tool error: …`.

## Gating

The `mcp` tool is only registered for a request when **My Library** is ON
(`react.py::_build_manager`). Destructive ops (`delete_document`) are therefore
never reachable for plain chats or web-only chats, and never used for
conversation history (which uses the `motor` store directly).
