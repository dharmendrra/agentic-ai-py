"""Mongo MCP server (:8083) over SSE — official Python ``mcp`` SDK.

Exposes ``/sse`` (event stream) and ``/messages/`` (client->server POST) per the
MCP SSE transport, plus ``/health``. Tool set mirrors the Go server.

Run:  uvicorn mcp_server.app.server:app --port 8083
"""
from __future__ import annotations

import contextlib
from typing import Any, Dict

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from shared.config import get_settings

from .db import Mongo
from .handlers import Handlers, tool_definitions

settings = get_settings()

mongo = Mongo(settings.MONGO_URI, settings.MONGO_DB)
handlers = Handlers(mongo.db)

server: Server = Server("agentic-mcps")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=d["name"],
            description=d["description"],
            inputSchema=d["inputSchema"],
        )
        for d in tool_definitions()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[types.TextContent]:
    try:
        text = await handlers.dispatch(name, arguments or {})
    except Exception as exc:  # noqa: BLE001
        # MCP convention: surface tool errors as text content with isError.
        return [types.TextContent(type="text", text=f"tool error: {exc}")]
    return [types.TextContent(type="text", text=text)]


# ── SSE transport wiring ───────────────────────────────────────────────────
sse = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
    return Response()


async def health(_: Request):
    return JSONResponse({"status": "ok", "service": "mcp_server"})


@contextlib.asynccontextmanager
async def lifespan(_: Starlette):
    yield
    mongo.close()


app = Starlette(
    debug=False,
    lifespan=lifespan,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
        Route("/health", endpoint=health),
    ],
)
