"""Dual-mode enforcement gate models (text -> 14D -> contain -> decide).

Hand-written TS mirrors live in frontend/src/lib/types.ts — keep the pair in sync.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

ENFORCEMENT_MODES = ("projection", "refusal")


class EncodeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    context: str = ""


class EncodeResponse(BaseModel):
    vector: List[float]
    dimension_names: List[str]


class GateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    context: str = ""
    label: str = ""
    # None = inherit (client override, else engine setting)
    mode: Optional[str] = None
    max_reflections: Optional[int] = Field(default=None, ge=1, le=6)


class ReflectionStep(BaseModel):
    attempt: int
    text: str
    vector: List[float]
    max_residual: float
    violated_constraints: List[str]
    feasible: bool
    correction_magnitude: float
    note: str = ""


class WisdomReport(BaseModel):
    applied: bool
    overconfidence_detected: bool
    humility_added: bool
    validation_suggested: bool
    adjustments: List[str]


class GateResponse(BaseModel):
    decision: str  # permitted | corrected | revised | withheld
    mode: str  # projection | refusal
    mode_source: str  # request | client | engine
    profile_id: str
    profile_name: str
    client_name: Optional[str] = None
    dimension_names: List[str]
    encoded_vector: List[float]
    final_vector: Optional[List[float]] = None
    final_text: Optional[str] = None
    max_residual: float
    correction_magnitude: float
    alignment_score: float
    violated_constraints: List[str]
    attempts: int
    iterations: int
    steps: List[ReflectionStep]
    wisdom: WisdomReport
    latency_ms: float
    event_id: str
    withheld_reason: Optional[str] = None
