"""Token-budgeted tiered context assembly (plan §7).

Pure logic — unit tested. Never includes raw tool observations (those are
transient and never persisted). Builds:
  rolling summary  +  last K turns verbatim (newest-first fill under budget)
"""
from __future__ import annotations

from typing import Any, Dict, List


def estimate_tokens(text: str) -> int:
    """len/4 heuristic (same spirit as the plan)."""
    return (len(text) + 3) // 4


def assemble_history(
    summary: str,
    recent_messages: List[Dict[str, Any]],
    token_budget: int,
) -> str:
    """Assemble the conversation-context block.

    - ``recent_messages`` are the last K turns in chronological order.
    - Fill newest-first under ``token_budget``; drop oldest that don't fit.
    - Prepend the rolling summary (always kept; it is small and important).
    """
    parts: List[str] = []
    if summary.strip():
        parts.append(f"Conversation summary so far:\n{summary.strip()}")

    summary_tokens = estimate_tokens(parts[0]) if parts else 0
    remaining = max(0, token_budget - summary_tokens)

    kept: List[str] = []
    for msg in reversed(recent_messages):  # newest first
        role = msg.get("role", "user")
        content = msg.get("content", "")
        line = f"{role.capitalize()}: {content}"
        cost = estimate_tokens(line)
        if cost > remaining and kept:
            break
        kept.append(line)
        remaining -= cost
    kept.reverse()  # restore chronological order

    if kept:
        parts.append("Recent turns:\n" + "\n".join(kept))

    return "\n\n".join(parts)
