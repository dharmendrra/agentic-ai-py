from agent.app.prompts import (
    build_system_prompt,
    parse_action,
    parse_clarification,
    parse_final_answer,
)


def _p(use_web, use_library):
    return build_system_prompt(
        tool_section="- search_pdf: search\n",
        tool_names=["recall_history", "search_pdf"],
        max_steps=10,
        use_web=use_web,
        use_library=use_library,
    )


def test_branch_no_tools_suggests_web():
    p = _p(False, False)
    assert "No external sources" in p
    assert "enable the Web" in p


def test_branch_library_only_clarify_back():
    p = _p(False, True)
    assert "My Library only" in p
    assert "NEEDS_CLARIFICATION" in p
    assert "'book' field" in p
    assert "Do NOT use the web" in p


def test_branch_web_only():
    p = _p(True, False)
    assert "Web only" in p
    assert "Do NOT use the internal library" in p


def test_branch_both():
    p = _p(True, True)
    assert "Both My Library and the Web" in p
    assert "merge both" in p


def test_prompt_lists_tool_names_and_clarification():
    p = _p(False, True)
    assert "recall_history | search_pdf" in p
    assert "Clarification:" in p
    assert "Maximum 10 steps" in p


def test_parse_final_answer():
    assert parse_final_answer("Thought: ok\nFinal Answer: 42") == "42"
    assert parse_final_answer("no final here") is None


def test_parse_clarification():
    assert parse_clarification("Clarification: which book?") == "which book?"
    assert parse_clarification("nope") is None


def test_parse_action_plain_and_json():
    a = parse_action("Thought: x\nAction: search_pdf\nAction Input: dragons in winter")
    assert a == ("search_pdf", "dragons in winter")
    b = parse_action('Action: mcp\nAction Input: {"action": "list_tools"}')
    assert b == ("mcp", '{"action": "list_tools"}')


def test_parse_action_missing_returns_none():
    assert parse_action("Thought: just thinking") is None
    assert parse_action("Action: foo") is None  # no Action Input
