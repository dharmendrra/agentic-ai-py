import pytest

from agent.app.tools.mcp_tool import MCPTool


class FakeToolDef:
    def __init__(self, name, description, schema):
        self.name = name
        self.description = description
        self.inputSchema = schema


class FakeClient:
    def __init__(self):
        self.calls = []

    async def list_tools_raw(self):
        return [
            FakeToolDef(
                "query_documents",
                "Query documents",
                {"type": "object", "properties": {"collection": {"type": "string"}}, "required": ["collection"]},
            )
        ]

    async def call(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return f"called {tool_name} with {arguments}"


@pytest.mark.asyncio
async def test_list_tools_action():
    tool = MCPTool(FakeClient())
    out = await tool.execute('{"action":"list_tools"}')
    assert "Available MCP tools:" in out
    assert "query_documents" in out
    assert "*collection(string)" in out


@pytest.mark.asyncio
async def test_call_action_strips_action_field():
    client = FakeClient()
    tool = MCPTool(client)
    out = await tool.execute('{"action":"query_documents","collection":"tasks","limit":5}')
    assert client.calls == [("query_documents", {"collection": "tasks", "limit": 5})]
    assert "called query_documents" in out


@pytest.mark.asyncio
async def test_invalid_json_raises():
    tool = MCPTool(FakeClient())
    with pytest.raises(ValueError):
        await tool.execute("not json")


@pytest.mark.asyncio
async def test_missing_action_raises():
    tool = MCPTool(FakeClient())
    with pytest.raises(ValueError):
        await tool.execute('{"collection":"x"}')
