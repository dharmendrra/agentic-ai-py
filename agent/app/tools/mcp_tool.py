"""mcp tool — the agent's single interface to the Mongo MCP server.

Parity with the Go mcp_tool.go: input is JSON with an ``action`` field.
  {"action": "list_tools"}                 -> discover available operations
  {"action": "query_documents", ...}       -> call that operation (rest = params)
"""
from __future__ import annotations

import json
from typing import Any, Dict

from .base import format_input_schema
from .mcp_client import MCPClient


class MCPTool:
    def __init__(self, client: MCPClient):
        self.client = client

    def name(self) -> str:
        return "mcp"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": "mcp",
            "description": (
                "Access MongoDB database operations via the Model Context Protocol "
                "(part of My Library). Use action:'list_tools' to discover available "
                "operations, or action:'<operation>' (e.g. query_documents, "
                "insert_document, update_document, delete_document, list_collections) "
                "with operation-specific parameters."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "'list_tools' to discover operations, or the name of an "
                            "MCP tool to execute."
                        ),
                    }
                },
                "required": ["action"],
            },
        }

    async def execute(self, input: str) -> str:
        try:
            req: Dict[str, Any] = json.loads(input)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid MCP tool input: {exc}") from exc

        action = req.get("action")
        if not isinstance(action, str):
            raise ValueError("action field required and must be a string")

        if action == "list_tools":
            return await self._list_tools()
        params = {k: v for k, v in req.items() if k != "action"}
        return await self.client.call(action, params)

    async def _list_tools(self) -> str:
        tools = await self.client.list_tools_raw()
        lines = ["Available MCP tools:", ""]
        for t in tools:
            lines.append(f"- {t.name}: {t.description}")
            schema = getattr(t, "inputSchema", None)
            props = format_input_schema(schema)
            if props:
                lines.append(f"  Required: {props}")
            lines.append("")
        return "\n".join(lines)
