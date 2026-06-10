from shared.config import Settings


def test_ollama_when_no_anthropic():
    s = Settings()
    assert s.use_anthropic is False


def test_ollama_when_credits_false():
    s = Settings(ANTHROPIC_API_KEY="sk-ant-x", ANTHROPIC_MODEL="claude", ANTHROPIC_CREDIT_BALANCE=False)
    assert s.use_anthropic is False


def test_ollama_when_model_missing():
    s = Settings(ANTHROPIC_API_KEY="sk-ant-x", ANTHROPIC_CREDIT_BALANCE=True)
    assert s.use_anthropic is False


def test_anthropic_when_all_set():
    s = Settings(
        ANTHROPIC_API_KEY="sk-ant-x",
        ANTHROPIC_MODEL="claude-haiku-4-5",
        ANTHROPIC_CREDIT_BALANCE=True,
    )
    assert s.use_anthropic is True
