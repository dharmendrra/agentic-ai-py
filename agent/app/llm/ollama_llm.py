"""Ollama LLM backend (async httpx → /api/generate, non-streaming)."""
from __future__ import annotations

import httpx


class OllamaLLM:
    def __init__(self, host: str, model: str, max_tokens: int, timeout: float = 120.0):
        self.host = host.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    def model_name(self) -> str:
        return self.model

    async def call(self, system: str, user: str) -> str:
        prompt = system + "\n\n" + user
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": self.max_tokens, "temperature": 0.7},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.host}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data.get("response", "")
