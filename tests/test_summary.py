import pytest

from agent.app.summary import format_messages_for_summary, maybe_summarize


class FakeSettings:
    SUMMARY_TRIGGER_TURNS = 2  # trigger at >4 messages
    HISTORY_TURNS = 1          # keep last 2 messages


class FakeLLM:
    def __init__(self):
        self.called = False

    def model_name(self):
        return "fake"

    async def call(self, system, user):
        self.called = True
        self.last_user = user
        return "ROLLED SUMMARY"


class FakeStore:
    def __init__(self, n_msgs, summary="", upto=0):
        self._msgs = [
            {"seq": i + 1, "role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
            for i in range(n_msgs)
        ]
        self._summary = summary
        self._upto = upto
        self.updated = None

    async def count_messages(self, conv_id):
        return len(self._msgs)

    async def get_conversation(self, conv_id):
        return {"summary": self._summary, "summary_upto_seq": self._upto}

    async def get_conversation_messages(self, conv_id):
        return self._msgs

    async def update_summary(self, conv_id, summary, upto_seq):
        self.updated = (summary, upto_seq)


def test_format_messages():
    out = format_messages_for_summary([{"role": "user", "content": "hi"}])
    assert out == "User: hi"


@pytest.mark.asyncio
async def test_no_summary_below_trigger():
    store = FakeStore(n_msgs=3)
    llm = FakeLLM()
    await maybe_summarize(FakeSettings(), llm, store, "c1")
    assert llm.called is False
    assert store.updated is None


@pytest.mark.asyncio
async def test_summarizes_above_trigger():
    # 8 messages, keep last 2 -> fold seqs 1..6
    store = FakeStore(n_msgs=8)
    llm = FakeLLM()
    await maybe_summarize(FakeSettings(), llm, store, "c1")
    assert llm.called is True
    assert store.updated is not None
    summary, upto = store.updated
    assert summary == "ROLLED SUMMARY"
    assert upto == 6  # max_seq(8) - keep(2)


@pytest.mark.asyncio
async def test_does_not_refold_already_summarized():
    # upto already past the cutoff -> nothing new to fold
    store = FakeStore(n_msgs=8, upto=6)
    llm = FakeLLM()
    await maybe_summarize(FakeSettings(), llm, store, "c1")
    assert llm.called is False
