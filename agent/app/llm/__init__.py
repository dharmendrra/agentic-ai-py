"""LLM backend selection (same rule as Go)."""
from __future__ import annotations

from shared.config import Settings

from .anthropic_llm import AnthropicLLM
from .base import LLM
from .ollama_llm import OllamaLLM


def select_llm(settings: Settings) -> LLM:
    """Anthropic only when key + model + credit-balance all set; else Ollama."""
    if settings.use_anthropic:
        return AnthropicLLM(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.MAX_TOKENS,
        )
    return OllamaLLM(
        host=settings.OLLAMA_HOST,
        model=settings.OLLAMA_MODEL,
        max_tokens=settings.MAX_TOKENS,
        timeout=settings.OLLAMA_TIMEOUT,
    )


__all__ = ["LLM", "AnthropicLLM", "OllamaLLM", "select_llm"]
