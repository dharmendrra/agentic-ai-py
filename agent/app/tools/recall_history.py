"""recall_history tool — read-only, conversation-scoped deep recall.

The backend injects ``conv_id`` (the model can never target another
conversation) and a ConversationStore. Modes:
  - all       : every user message in order
  - first_n   : first N user messages (param ``n``, default 3)
  - search    : messages whose content matches ``query`` (case-insensitive)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


class RecallHistoryTool:
    def __init__(self, store: Any, conv_id: str):
        self.store = store
        self.conv_id = conv_id

    def name(self) -> str:
        return "recall_history"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": "recall_history",
            "description": (
                "Read-only recall of THIS conversation's earlier messages (for "
                "questions like 'what did I ask first' or 'summarize our chat'). "
                "Cannot modify anything and cannot see other conversations."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "One of: all | first_n | search",
                    },
                    "n": {
                        "type": "number",
                        "description": "For first_n: how many earliest user messages (default 3)",
                    },
                    "query": {
                        "type": "string",
                        "description": "For search: term to match against message content",
                    },
                },
                "required": ["mode"],
            },
        }

    async def execute(self, input: str) -> str:
        args = _parse_args(input)
        mode = args.get("mode", "all")

        if mode == "first_n":
            n = int(args.get("n", 3) or 3)
            msgs = await self.store.get_first_n_user_messages(self.conv_id, n)
            return _format(msgs, f"First {n} user messages")
        if mode == "search":
            term = str(args.get("query", "")).strip()
            if not term:
                return "recall_history: 'query' is required for mode=search"
            msgs = await self.store.search_messages(self.conv_id, term)
            return _format(msgs, f"Messages matching '{term}'")
        # default: all
        msgs = await self.store.get_all_user_messages(self.conv_id)
        return _format(msgs, "All user messages")


def _parse_args(input: str) -> Dict[str, Any]:
    s = input.strip()
    if not s:
        return {"mode": "all"}
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    # Plain text → treat as mode keyword if recognized, else a search term.
    if s in ("all", "first_n", "search"):
        return {"mode": s}
    return {"mode": "search", "query": s}


def _format(msgs: List[Dict[str, Any]], header: str) -> str:
    if not msgs:
        return f"{header}: (none found)"
    lines = [f"{header}:"]
    for m in msgs:
        seq = m.get("seq", "?")
        role = m.get("role", "user")
        content = m.get("content", "")
        lines.append(f"[{seq}] {role}: {content}")
    return "\n".join(lines)
