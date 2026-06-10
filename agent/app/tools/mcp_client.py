"""Persistent MCP client over SSE (official Python ``mcp`` SDK).

Holds one long-lived ClientSession to the Mongo MCP server (:8083). Because the
SSE transport and session are async context managers, we keep them open for the
process lifetime via a background task and expose ``list_tools`` / ``call``.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional


class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self._session = None
        self._task: Optional[asyncio.Task] = None
        self._ready = asyncio.Event()
        self._closed = asyncio.Event()
        self._error: Optional[Exception] = None

    async def connect(self) -> None:
        """Open the SSE session in a background task and wait until initialized."""
        self._task = asyncio.create_task(self._run())
        await self._ready.wait()
        if self._error:
            raise self._error

    async def _run(self) -> None:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        try:
            async with sse_client(f"{self.server_url}/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    # keep the session alive until close() is requested
                    await self._closed.wait()
        except Exception as exc:  # noqa: BLE001
            self._error = exc
            self._ready.set()

    async def list_tools_raw(self) -> List[Any]:
        result = await self._session.list_tools()
        return list(result.tools)

    async def call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        result = await self._session.call_tool(tool_name, arguments or {})
        if getattr(result, "isError", False):
            return f"tool error: {_extract_text(result)}"
        return _extract_text(result)

    async def close(self) -> None:
        self._closed.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass


def _extract_text(result: Any) -> str:
    parts: List[str] = []
    for c in getattr(result, "content", []) or []:
        text = getattr(c, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)
