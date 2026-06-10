"""ReAct loop + memory/context assembly (plan §6.5, §7).

run_react:
  1. Build per-request tool set (always recall_history; library -> search_pdf +
     mcp; web -> web_search).
  2. Budgeted prompt: branched system + rolling summary + last K turns + query.
  3. ReAct loop (Thought/Action/Action Input/Observation), observations transient.
  4. Clarify-back: 'Clarification:' exits with needs_clarification=True.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from .context import assemble_history
from .prompts import (
    build_system_prompt,
    parse_action,
    parse_clarification,
    parse_final_answer,
)
from .tools.base import Manager
from .tools.mcp_tool import MCPTool
from .tools.recall_history import RecallHistoryTool
from .tools.web_search import WEB_SRC_MARKER

log = logging.getLogger("agent.react")


def _ordered_sources(used: set) -> list:
    """Stable source order for the provenance label."""
    return [s for s in ("pdf", "web", "mongo") if s in used]


def split_web_citations(result: str):
    """Separate a web_search observation from its trailing [[WEBSRC]] marker.
    Returns (cleaned_text, [{title, url}, ...])."""
    idx = result.find(WEB_SRC_MARKER)
    if idx < 0:
        return result, []
    cleaned = result[:idx].strip()
    raw = result[idx + len(WEB_SRC_MARKER):]
    cites = []
    for item in raw.split(" || "):
        parts = item.split(" :: ", 1)
        if len(parts) == 2 and parts[1].strip():
            cites.append({"title": parts[0].strip(), "url": parts[1].strip()})
    return cleaned, cites


class ReActRunner:
    def __init__(self, settings, llm, store, base_tools):
        """base_tools: dict with optional keys 'search_pdf', 'web_search', 'mcp_client'."""
        self.settings = settings
        self.llm = llm
        self.store = store
        self.base_tools = base_tools

    def _build_manager(self, conv_id: str, use_web: bool, use_library: bool) -> Manager:
        mgr = Manager()
        # recall_history is always available, conversation-scoped.
        mgr.register(RecallHistoryTool(self.store, conv_id))
        if use_library:
            if self.base_tools.get("search_pdf"):
                mgr.register(self.base_tools["search_pdf"])
            if self.base_tools.get("mcp_client"):
                mgr.register(MCPTool(self.base_tools["mcp_client"]))
        if use_web:
            if self.base_tools.get("web_search"):
                mgr.register(self.base_tools["web_search"])
        return mgr

    async def run(
        self, conv_id: str, query: str, use_web: bool, use_library: bool
    ) -> Tuple[str, bool, list, list]:
        mgr = self._build_manager(conv_id, use_web, use_library)
        system_prompt = build_system_prompt(
            mgr.build_prompt_section(),
            mgr.names(),
            self.settings.MAX_STEPS,
            use_web,
            use_library,
        )

        # Budgeted conversation context (excludes the current user turn, which is
        # appended by the caller before run()).
        conv = await self.store.get_conversation(conv_id)
        summary = (conv or {}).get("summary", "") or ""
        recent = await self.store.get_recent_messages(
            conv_id, self.settings.HISTORY_TURNS * 2
        )
        # Drop the just-appended current user message from the verbatim window
        # so it isn't duplicated with the explicit "Current question" line.
        if recent and recent[-1].get("role") == "user" and recent[-1].get("content") == query:
            recent = recent[:-1]
        history_block = assemble_history(
            summary, recent, self.settings.HISTORY_TOKEN_BUDGET
        )

        messages: List[str] = []
        if history_block:
            messages.append(history_block)
        messages.append(f"Current question: {query}")

        answer = ""
        citations: List[dict] = []
        used_sources: set = set()
        for step in range(1, self.settings.MAX_STEPS + 1):
            user = "\n\n".join(messages)
            log.info("[AGENT] step %d/%d via %s", step, self.settings.MAX_STEPS,
                     self.llm.model_name())
            response = await self.llm.call(system_prompt, user)
            messages.append(response)

            clar = parse_clarification(response)
            if clar is not None:
                return clar, True, _ordered_sources(used_sources), citations

            final = parse_final_answer(response)
            if final is not None:
                return final, False, _ordered_sources(used_sources), citations

            act = parse_action(response)

            # Plain-LLM mode: with no retrieval tools enabled there is nothing to
            # iterate on, so a direct response (no Action) IS the answer — accept it
            # instead of looping to MAX_STEPS. Weak local models often answer
            # without the "Final Answer:" prefix. See plan §6.5 (no-tools branch).
            if act is None and not use_web and not use_library:
                log.info("[AGENT] no tools active and no Action - treating response as final answer")
                return response.strip(), False, _ordered_sources(used_sources), citations

            if act is not None:
                action, action_input = act
                # Some models emit "Action: Final Answer" instead of "Final Answer:".
                # Treat it as the final answer, not a nonexistent tool.
                if action.lower() in ("final", "finalanswer"):
                    i = response.find("Action Input:")
                    final_text = response[i + len("Action Input:"):].strip() if i >= 0 else action_input
                    return final_text, False, _ordered_sources(used_sources), citations
                try:
                    observation = await mgr.execute(action, action_input)
                except Exception as exc:  # noqa: BLE001
                    observation = f"Error: {exc}"
                if action == "web_search":
                    observation, cites = split_web_citations(observation)
                    citations.extend(cites)
                    used_sources.add("web")
                elif action == "search_pdf":
                    if not observation.startswith("[PDF_EMPTY") and "NEEDS_CLARIFICATION" not in observation:
                        used_sources.add("pdf")
                elif action == "mcp":
                    used_sources.add("mongo")
                # observations are transient — appended to the prompt, never stored
                messages.append(f"Observation: {observation}")
            else:
                log.info("[AGENT] step %d: no Action/Input parsed", step)

        # Max steps reached without a Final Answer.
        if not answer:
            answer = messages[-1] if messages else "Unable to generate an answer."
        return answer, False, _ordered_sources(used_sources), citations
