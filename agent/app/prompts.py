"""System-prompt builder + ReAct response parsing (pure logic, unit-tested)."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_ACTION_RE = re.compile(r"Action:\s*(\w+)")
_INPUT_RE = re.compile(r"Action Input:\s*(.+?)(?:\n|$)")


def build_system_prompt(
    tool_section: str,
    tool_names: List[str],
    max_steps: int,
    use_web: bool,
    use_library: bool,
) -> str:
    """Branch the system prompt by the Web / My Library toggles (plan §6.5)."""
    names = " | ".join(tool_names)

    if not use_web and not use_library:
        guidance = (
            "RETRIEVAL MODE: No external sources are enabled. Answer from your own "
            "knowledge only. If you are unsure or the question needs current/"
            "external information, say so and suggest the user enable the Web "
            "toggle. You may still use recall_history to reference earlier turns."
        )
    elif use_library and not use_web:
        guidance = (
            "RETRIEVAL MODE: My Library only (internal sources). Use search_pdf and "
            "the mcp database tools. Do NOT use the web. When the user names a book, "
            "pass it in search_pdf's 'book' field (JSON input) to narrow the search. "
            "If a result is '[NEEDS_CLARIFICATION|...]', do not guess — respond with "
            "Clarification: listing the candidate books. Cite the book shown in each "
            "[book: ...] tag."
        )
    elif use_web and not use_library:
        guidance = (
            "RETRIEVAL MODE: Web only. Use web_search for external information. Do "
            "NOT use the internal library tools."
        )
    else:  # both
        guidance = (
            "RETRIEVAL MODE: Both My Library and the Web are enabled. Prefer "
            "search_pdf / mcp for the user's own documents, use web_search for "
            "external or current info, and merge both into a single answer. When the "
            "user names a book, pass it in search_pdf's 'book' field. If a result is "
            "'[NEEDS_CLARIFICATION|...]', respond with Clarification: listing the "
            "candidate books. Cite the book shown in each [book: ...] tag."
        )

    return f"""You are a helpful conversational assistant with memory of the current conversation.

{guidance}

AVAILABLE TOOLS:
{tool_section}
REASONING FORMAT (ReAct):
You MUST follow this exact format for each reasoning step:

Thought: [your reasoning about what to do next]
Action: {names}
Action Input: [plain text query, OR a JSON object — see rules]
Observation: [result from the tool]

When you have sufficient information:
Final Answer: [your complete answer]

If My Library is on and you cannot determine which specific book the user means, instead of guessing respond with:
Clarification: [a short question asking which book, offering the candidate titles]

RULES:
- Follow Thought-Action-Observation format exactly
- DB/recall tool inputs (mcp, recall_history) must be valid JSON objects
- web_search input is plain text; search_pdf is plain text for a general search OR a JSON object {{"query":"...","book":"..."}} — use the JSON form with "book" whenever the user names a specific book
- Never invent tool names — only use the ones listed above
- Maximum {max_steps} steps allowed"""


def parse_final_answer(response: str) -> Optional[str]:
    if "Final Answer:" in response:
        return response.split("Final Answer:", 1)[1].strip()
    return None


def parse_clarification(response: str) -> Optional[str]:
    if "Clarification:" in response:
        return response.split("Clarification:", 1)[1].strip()
    return None


def parse_action(response: str) -> Optional[Tuple[str, str]]:
    """Return (action, input) if both present, else None."""
    if "Action:" not in response or "Action Input:" not in response:
        return None
    a = _ACTION_RE.search(response)
    i = _INPUT_RE.search(response)
    if not a or not i:
        return None
    return a.group(1), i.group(1).strip()
