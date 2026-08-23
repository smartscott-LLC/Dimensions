"""Coaching chat: live LLM turns gated by the polytope before release.

TS mirrors live in frontend/src/lib/types.ts — keep the pair in sync.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatSession(BaseModel):
    id: str = Field(default_factory=_uid)
    title: str = "New session"
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    profile_id: str
    profile_name: str
    mode: Optional[str] = None  # None = inherit client/engine mode
    model: str = "claude-sonnet-4-5-20250929"
    turns: int = 0
    withheld: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New session", max_length=120)
    mode: Optional[str] = None


class ChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ChatTurn(BaseModel):
    id: str = Field(default_factory=_uid)
    session_id: str
    user_text: str
    draft_text: str  # what the model produced, pre-enforcement
    released_text: Optional[str] = None  # None when withheld
    decision: str  # permitted | corrected | revised | withheld
    mode: str
    encoded_vector: List[float]
    final_vector: Optional[List[float]] = None
    dimension_names: List[str] = []
    violated_constraints: List[str] = []
    why: List[str] = []  # human-readable "why it tripped" lines
    suggested_rewrite: Optional[str] = None
    max_residual: float = 0.0
    correction_magnitude: float = 0.0
    alignment_score: float = 1.0
    attempts: int = 1
    steps: List[Dict[str, Any]] = []
    wisdom: List[str] = []
    withheld_reason: Optional[str] = None
    latency_ms: float = 0.0
    event_id: str = ""
    created_at: datetime = Field(default_factory=_now)
