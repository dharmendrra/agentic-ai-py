"""web_search tool — Tavily, returns the synthesized ``answer`` field.

Parity with the Go web_search.go (uses Tavily's ``answer``). Uses the POST API
with include_answer=true; falls back gracefully when unconfigured.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

import httpx

# Machine-readable web-sources marker appended to a web_search observation.
# react.py parses + strips it into clickable citations (see split_web_citations).
WEB_SRC_MARKER = "[[WEBSRC]]"


class WebSearchTool:
    def __init__(self, api_key: str, max_retries: int):
        self.api_key = api_key
        self.max_retries = max_retries

    def name(self) -> str:
        return "web_search"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": "web_search",
            "description": (
                "Search the internet (Tavily). Use when the answer isn't in My "
                "Library or needs up-to-date / external verification."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find information on the internet",
                    }
                },
                "required": ["query"],
            },
        }

    async def execute(self, input: str) -> str:
        if not self.api_key or self.api_key.startswith("tvly-..."):
            return "Web search not configured (missing TAVILY_API_KEY)"
        query = _extract_query(input)
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": 3,
            "include_answer": True,
        }
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post("https://api.tavily.com/search", json=payload)
                    if resp.status_code != 200:
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(attempt + 1)
                            continue
                        raise RuntimeError(f"web_search returned status {resp.status_code}")
                    data = resp.json()
                    answer = data.get("answer") or ""
                    results = data.get("results") or []
                    parts = []
                    for r in results:
                        url = r.get("url")
                        if url:
                            parts.append(f"{(r.get('title') or '').strip()} :: {url}")
                    text = answer or (results[0].get("title", "") if results else "")
                    if not text and not parts:
                        return "No web results found"
                    if parts:
                        text = f"{text}\n\n{WEB_SRC_MARKER}" + " || ".join(parts)
                    return text
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(attempt + 1)
                    continue
        raise RuntimeError(
            f"web_search failed after {self.max_retries} retries: {last_exc}"
        )


def _extract_query(input: str) -> str:
    s = input.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict) and "query" in obj:
                return str(obj["query"])
        except json.JSONDecodeError:
            pass
    return s
