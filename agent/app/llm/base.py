"""LLM abstraction so Anthropic and Ollama are interchangeable."""
from __future__ import annotations

from typing import Protocol


class LLM(Protocol):
    def model_name(self) -> str: ...

    async def call(self, system: str, user: str) -> str: ...
