"""Ollama embeddings client (async httpx).

Calls ``POST {OLLAMA_HOST}/api/embeddings`` with ``{model, prompt}`` per
embedding. Ollama returns ``{"embedding": [float, ...]}``.
"""
from __future__ import annotations

from typing import List

import httpx


class EmbeddingsClient:
    def __init__(self, host: str, model: str, timeout: float = 60.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def embed(self, text: str) -> List[float]:
        url = f"{self.host}/api/embeddings"
        payload = {"model": self.model, "prompt": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        embedding = data.get("embedding")
        if not embedding:
            raise ValueError(f"Ollama returned no embedding for model '{self.model}'")
        return embedding

    async def embed_many(self, texts: List[str]) -> List[List[float]]:
        # Ollama's /api/embeddings is single-prompt; embed sequentially to avoid
        # overwhelming a local instance. Callers chunk modestly.
        out: List[List[float]] = []
        for t in texts:
            out.append(await self.embed(t))
        return out
