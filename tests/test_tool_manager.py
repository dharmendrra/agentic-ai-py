import pytest

from agent.app.tools.base import Manager, format_input_schema


class DummyTool:
    def __init__(self, name, required=None, props=None):
        self._name = name
        self._props = props or {}
        self._required = required or []

    def name(self):
        return self._name

    def schema(self):
        return {
            "name": self._name,
            "description": f"desc for {self._name}",
            "input_schema": {
                "type": "object",
                "properties": self._props,
                "required": self._required,
            },
        }

    async def execute(self, input):
        return f"{self._name}:{input}"


def test_format_input_schema_required_marker():
    schema = {
        "properties": {"query": {"type": "string"}, "limit": {"type": "number"}},
        "required": ["query"],
    }
    out = format_input_schema(schema)
    assert "*query(string)" in out
    assert "limit(number)" in out
    # sorted output
    assert out == ", ".join(sorted(out.split(", ")))


def test_registration_order_preserved():
    m = Manager()
    m.register(DummyTool("a"))
    m.register(DummyTool("b"))
    m.register(DummyTool("a"))  # re-register doesn't duplicate order
    assert m.names() == ["a", "b"]


def test_build_prompt_section():
    m = Manager()
    m.register(DummyTool("search_pdf", required=["query"], props={"query": {"type": "string"}}))
    section = m.build_prompt_section()
    assert "- search_pdf: desc for search_pdf" in section
    assert "Input: *query(string)" in section


@pytest.mark.asyncio
async def test_execute_and_not_found():
    m = Manager()
    m.register(DummyTool("x"))
    assert await m.execute("x", "hi") == "x:hi"
    with pytest.raises(ValueError):
        await m.execute("missing", "hi")
