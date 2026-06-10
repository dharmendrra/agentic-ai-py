import pytest

from agent.app.react import ReActRunner


class FakeSettings:
    MAX_STEPS = 5
    MAX_RETRIES = 1
    HISTORY_TURNS = 6
    HISTORY_TOKEN_BUDGET = 6000


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def model_name(self):
        return "fake"

    async def call(self, system, user):
        self.prompts.append((system, user))
        return self.responses.pop(0)


class FakeStore:
    def __init__(self, recent=None, summary=""):
        self._recent = recent or []
        self._summary = summary
        self.appended = []

    async def get_conversation(self, conv_id):
        return {"summary": self._summary}

    async def get_recent_messages(self, conv_id, k):
        return self._recent

    async def get_all_user_messages(self, conv_id):
        return [m for m in self._recent if m["role"] == "user"]


class EchoTool:
    def __init__(self, name):
        self._name = name
        self.calls = []

    def name(self):
        return self._name

    def schema(self):
        return {
            "name": self._name,
            "description": "echo",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        }

    async def execute(self, input):
        self.calls.append(input)
        return f"OBS[{self._name}]: result for {input}"


@pytest.mark.asyncio
async def test_simple_final_answer_no_tools():
    llm = FakeLLM(["Thought: easy\nFinal Answer: 42"])
    store = FakeStore()
    runner = ReActRunner(FakeSettings(), llm, store, {})
    answer, clar, _src, _cites = await runner.run("c1", "what is 6*7", use_web=False, use_library=False)
    assert answer == "42"
    assert clar is False


@pytest.mark.asyncio
async def test_clarify_back_exits():
    llm = FakeLLM(["Clarification: Do you mean Game of Thrones or The Hobbit?"])
    runner = ReActRunner(FakeSettings(), llm, FakeStore(), {})
    answer, clar, _src, _cites = await runner.run("c1", "tell me about dragons", use_web=False, use_library=True)
    assert clar is True
    assert "Game of Thrones" in answer


@pytest.mark.asyncio
async def test_tool_call_then_final():
    pdf = EchoTool("search_pdf")
    llm = FakeLLM([
        "Thought: search\nAction: search_pdf\nAction Input: dragons",
        "Thought: done\nFinal Answer: Dragons are big.",
    ])
    runner = ReActRunner(FakeSettings(), llm, FakeStore(), {"search_pdf": pdf})
    answer, clar, _src, _cites = await runner.run("c1", "dragons?", use_web=False, use_library=True)
    assert answer == "Dragons are big."
    assert pdf.calls == ["dragons"]
    # The 2nd LLM prompt must contain the transient observation.
    second_user = llm.prompts[1][1]
    assert "OBS[search_pdf]" in second_user


@pytest.mark.asyncio
async def test_library_off_means_no_pdf_tool():
    pdf = EchoTool("search_pdf")
    # model tries to use search_pdf but it's not registered -> error observation
    llm = FakeLLM([
        "Action: search_pdf\nAction Input: x",
        "Final Answer: fell back to own knowledge",
    ])
    runner = ReActRunner(FakeSettings(), llm, FakeStore(), {"search_pdf": pdf})
    answer, _c, _src, _cites = await runner.run("c1", "q", use_web=False, use_library=False)
    assert answer == "fell back to own knowledge"
    assert pdf.calls == []  # never called because not registered
    # observation should report tool-not-found error
    assert "not found" in llm.prompts[1][1]


@pytest.mark.asyncio
async def test_recall_history_always_available():
    # No toggles, but recall_history must be registered.
    captured = {}

    class CaptureLLM(FakeLLM):
        async def call(self, system, user):
            captured["system"] = system
            return "Final Answer: ok"

    runner = ReActRunner(FakeSettings(), CaptureLLM(["x"]), FakeStore(), {})
    await runner.run("c1", "q", use_web=False, use_library=False)
    assert "recall_history" in captured["system"]
