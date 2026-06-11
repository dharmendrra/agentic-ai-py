"""Agent service (:8082) — conversational ReAct agent.

Endpoints:
  POST   /api/agent/query
  GET    /api/conversations
  GET    /api/conversations/{id}
  DELETE /api/conversations/{id}
  GET    /                          chat UI
"""
from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .llm import select_llm
from .models import AgentRequest, AgentResponse
from .react import ReActRunner
from .store import ConversationStore
from .summary import maybe_summarize
from .tools.mcp_client import MCPClient
from .tools.pdf_search import PDFSearchTool
from .tools.web_search import WebSearchTool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent")

settings = get_settings()
STATIC_DIR = Path(__file__).parent / "static"
SHARED_STATIC = Path(__file__).resolve().parents[2] / "shared" / "static"

app = FastAPI(title="agentic-ai agent", version="0.1.0")

store = ConversationStore(settings.MONGO_URI, settings.MONGO_DB)
llm = select_llm(settings)

# Persistent base tools (reused across requests; gated per-request in react.py).
base_tools = {
    "search_pdf": PDFSearchTool(settings.SEARCH_ENDPOINT, settings.MAX_RETRIES),
    "web_search": WebSearchTool(settings.TAVILY_API_KEY, settings.MAX_RETRIES),
    "mcp_client": None,
}
runner = ReActRunner(settings, llm, store, base_tools)


@app.on_event("startup")
async def startup() -> None:
    log.info("[LLM] backend: %s", llm.model_name())
    client = MCPClient(settings.MCP_SERVER_URL)
    try:
        await client.connect()
        base_tools["mcp_client"] = client
        log.info("[MCP] connected to %s", settings.MCP_SERVER_URL)
    except Exception as exc:  # noqa: BLE001
        log.warning("[MCP] could not connect (%s) — mcp tool unavailable", exc)


@app.on_event("shutdown")
async def shutdown() -> None:
    client = base_tools.get("mcp_client")
    if client:
        with contextlib.suppress(Exception):
            await client.close()
    store.close()


def _title_from_query(query: str) -> str:
    t = query.strip().replace("\n", " ")
    return (t[:60] + "…") if len(t) > 60 else t or "New conversation"


@app.post("/api/agent/query", response_model=AgentResponse)
async def agent_query(req: AgentRequest) -> AgentResponse:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    # Create or look up the conversation.
    if req.conversation_id:
        conv = await store.get_conversation(req.conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        conv_id = req.conversation_id
        title = conv.get("title", "")
    else:
        title = _title_from_query(req.query)
        conv_id = await store.create_conversation(title)

    # Persist the user message (final text only).
    await store.append_message(conv_id, "user", req.query)

    # Run the ReAct loop.
    try:
        answer, needs_clarification, sources, citations = await runner.run(
            conv_id, req.query, req.use_web, req.use_library
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[AGENT] runner.run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Persist the assistant message (with the sources + citations used this turn).
    await store.append_message(conv_id, "assistant", answer, sources, citations)

    # Maybe roll older turns into the summary.
    with contextlib.suppress(Exception):
        await maybe_summarize(settings, llm, store, conv_id)

    return AgentResponse(
        answer=answer,
        conversation_id=conv_id,
        title=title,
        sources=sources,
        citations=citations,
        needs_clarification=needs_clarification,
    )


@app.get("/api/conversations")
async def list_conversations():
    return await store.list_conversations()


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = await store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    msgs = await store.get_conversation_messages(conv_id)
    return {
        "id": conv_id,
        "title": conv.get("title", ""),
        "summary": conv.get("summary", ""),
        "messages": [
            {
                "seq": m.get("seq"),
                "role": m.get("role"),
                "content": m.get("content"),
                "sources": m.get("sources"),
                "citations": m.get("citations"),
            }
            for m in msgs
        ],
    }


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    ok = await store.delete_conversation(conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"deleted": True}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent"}


# Single shared assets (one stylesheet for every page — no per-page copies).
if SHARED_STATIC.exists():
    app.mount("/assets", StaticFiles(directory=str(SHARED_STATIC)), name="assets")
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
