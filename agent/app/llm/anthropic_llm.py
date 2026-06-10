"""Anthropic LLM backend (official async SDK)."""
from __future__ import annotations


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        from anthropic import AsyncAnthropic

        self.model = model
        self.max_tokens = max_tokens
        self._client = AsyncAnthropic(api_key=api_key)

    def model_name(self) -> str:
        return self.model

    async def call(self, system: str, user: str) -> str:
        msg = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""
