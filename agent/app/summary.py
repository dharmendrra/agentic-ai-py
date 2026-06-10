"""Rolling-summary maintenance (plan §7).

When a conversation grows past SUMMARY_TRIGGER_TURNS turns, fold everything
older than the last K turns into ``conversations.summary`` via the LLM, advancing
``summary_upto_seq``. Keeps prompts cheap while full history stays in Mongo.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

log = logging.getLogger("agent.summary")

_SUMMARY_SYSTEM = (
    "You maintain a running summary of a conversation. Given the prior summary "
    "and a batch of older messages, produce an updated, concise summary that "
    "preserves key facts, decisions, and the user's goals. Output only the "
    "summary text."
)


def format_messages_for_summary(messages: List[Dict[str, Any]]) -> str:
    lines = []
    for m in messages:
        lines.append(f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}")
    return "\n".join(lines)


async def maybe_summarize(settings, llm, store, conv_id: str) -> None:
    """Summarize older turns if the conversation exceeded the trigger.

    A "turn" here = one user+assistant pair, so messages ~= 2*turns.
    """
    total = await store.count_messages(conv_id)
    trigger_msgs = settings.SUMMARY_TRIGGER_TURNS * 2
    if total <= trigger_msgs:
        return

    conv = await store.get_conversation(conv_id)
    if conv is None:
        return
    prior_summary = conv.get("summary", "") or ""
    upto = conv.get("summary_upto_seq", 0) or 0

    keep_msgs = settings.HISTORY_TURNS * 2
    # Summarize messages between (upto, total-keep_msgs].
    all_msgs = await store.get_conversation_messages(conv_id)
    if not all_msgs:
        return
    max_seq = all_msgs[-1]["seq"]
    cutoff_seq = max_seq - keep_msgs
    to_fold = [m for m in all_msgs if upto < m["seq"] <= cutoff_seq]
    if not to_fold:
        return

    user_prompt = (
        f"Prior summary:\n{prior_summary or '(none)'}\n\n"
        f"Older messages to fold in:\n{format_messages_for_summary(to_fold)}"
    )
    try:
        new_summary = await llm.call(_SUMMARY_SYSTEM, user_prompt)
    except Exception as exc:  # noqa: BLE001
        log.warning("[SUMMARY] failed: %s", exc)
        return
    new_summary = new_summary.strip()
    if new_summary:
        await store.update_summary(conv_id, new_summary, cutoff_seq)
        log.info("[SUMMARY] updated conv %s upto_seq=%d", conv_id, cutoff_seq)
