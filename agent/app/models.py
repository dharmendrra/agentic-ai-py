"""Pydantic models for the agent API + conversation store."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    use_web: bool = False
    use_library: bool = False


class AgentResponse(BaseModel):
    answer: str
    conversation_id: str
    title: str
    sources: List[str] = []
    citations: List[dict] = []
    needs_clarification: bool = False


class Message(BaseModel):
    seq: int
    role: str  # "user" | "assistant"
    content: str
    sources: Optional[List[Any]] = None
    created_at: Optional[datetime] = None


class ConversationSummary(BaseModel):
    id: str = Field(..., alias="_id")
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class ConversationDetail(BaseModel):
    id: str
    title: str
    summary: str = ""
    messages: List[Message] = []
