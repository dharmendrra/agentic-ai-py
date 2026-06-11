"""Shared config loader.

All three services read the same ``config.json`` (gitignored) at the repo root,
falling back to ``config.example.json``. Each service picks the fields it needs.
Environment variables of the same name override file values.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Repo root = parent of the ``shared`` package directory.
REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    # LLM
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4:e4b"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = ""
    ANTHROPIC_CREDIT_BALANCE: bool = False
    MAX_STEPS: int = 6
    MAX_RETRIES: int = 3
    MAX_TOKENS: int = 1024
    OLLAMA_TIMEOUT: float = 300.0

    # Embeddings + Pinecone
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIM: int = 768
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "agentic-pdf"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    RETRIEVAL_TOP_K: int = 3

    # Web
    TAVILY_API_KEY: str = ""

    # Service URLs
    SEARCH_ENDPOINT: str = "http://localhost:8081/api/search"
    MCP_SERVER_URL: str = "http://localhost:8083"

    # Mongo
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "agentic_mcps"

    # Conversation memory
    HISTORY_TURNS: int = 6
    HISTORY_TOKEN_BUDGET: int = 6000
    SUMMARY_TRIGGER_TURNS: int = 8

    @property
    def use_anthropic(self) -> bool:
        """LLM backend rule (same as Go): Anthropic only when key + model + credits all set."""
        return bool(
            self.ANTHROPIC_API_KEY
            and self.ANTHROPIC_MODEL
            and self.ANTHROPIC_CREDIT_BALANCE
        )


def _read_file_config() -> dict[str, Any]:
    for name in ("config.json", "config.example.json"):
        path = REPO_ROOT / name
        if path.exists():
            with path.open() as fh:
                return json.load(fh)
    return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data = _read_file_config()
    # env overrides
    for field in Settings.model_fields:
        if field in os.environ:
            data[field] = os.environ[field]
    return Settings(**data)
