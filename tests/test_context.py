from agent.app.context import assemble_history, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 8) == 2


def _msgs(n):
    out = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        out.append({"role": role, "content": f"message number {i}"})
    return out


def test_summary_always_included():
    block = assemble_history("prior summary here", [], 1000)
    assert "Conversation summary so far:" in block
    assert "prior summary here" in block


def test_recent_turns_chronological():
    block = assemble_history("", _msgs(4), 10000)
    # order preserved: message 0 appears before message 3
    assert block.index("message number 0") < block.index("message number 3")


def test_budget_drops_oldest_first():
    msgs = _msgs(10)
    # Tiny budget: only the newest message(s) survive; the oldest are dropped.
    block = assemble_history("", msgs, estimate_tokens("Assistant: message number 9") + 1)
    assert "message number 9" in block
    assert "message number 0" not in block


def test_observations_never_present():
    # assemble_history only ever sees stored messages (final text); ensure it
    # doesn't fabricate observation markers.
    block = assemble_history("sum", _msgs(2), 1000)
    assert "Observation:" not in block
