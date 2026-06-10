import pytest

from agent.app.tools.recall_history import RecallHistoryTool, _parse_args


class FakeStore:
    def __init__(self):
        self.user_msgs = [
            {"seq": 1, "role": "user", "content": "what is python"},
            {"seq": 3, "role": "user", "content": "tell me about dragons"},
            {"seq": 5, "role": "user", "content": "python decorators"},
        ]
        self.all_msgs = self.user_msgs

    async def get_all_user_messages(self, conv_id):
        return self.user_msgs

    async def get_first_n_user_messages(self, conv_id, n):
        return self.user_msgs[:n]

    async def search_messages(self, conv_id, term):
        return [m for m in self.all_msgs if term.lower() in m["content"].lower()]


def test_parse_args_keywords_and_search():
    assert _parse_args("all") == {"mode": "all"}
    assert _parse_args("first_n") == {"mode": "first_n"}
    assert _parse_args('{"mode":"search","query":"x"}') == {"mode": "search", "query": "x"}
    # plain free text -> search
    assert _parse_args("dragons") == {"mode": "search", "query": "dragons"}
    assert _parse_args("") == {"mode": "all"}


@pytest.mark.asyncio
async def test_mode_all():
    tool = RecallHistoryTool(FakeStore(), "c1")
    out = await tool.execute('{"mode":"all"}')
    assert "what is python" in out
    assert "[1]" in out and "[5]" in out


@pytest.mark.asyncio
async def test_mode_first_n():
    tool = RecallHistoryTool(FakeStore(), "c1")
    out = await tool.execute('{"mode":"first_n","n":2}')
    assert "what is python" in out
    assert "python decorators" not in out


@pytest.mark.asyncio
async def test_mode_search():
    tool = RecallHistoryTool(FakeStore(), "c1")
    out = await tool.execute('{"mode":"search","query":"python"}')
    assert "what is python" in out
    assert "python decorators" in out
    assert "dragons" not in out


@pytest.mark.asyncio
async def test_search_requires_query():
    tool = RecallHistoryTool(FakeStore(), "c1")
    out = await tool.execute('{"mode":"search"}')
    assert "required" in out.lower()


def test_schema_is_read_only_and_scoped():
    tool = RecallHistoryTool(FakeStore(), "c1")
    s = tool.schema()
    assert s["name"] == "recall_history"
    assert "Cannot modify" in s["description"]
