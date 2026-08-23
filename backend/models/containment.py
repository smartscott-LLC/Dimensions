"""Pydantic v2 models for the 14D geometric containment framework.

Every model here has a hand-written TS mirror in frontend/src/lib/types.ts —
keep the pair in sync in the same edit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

DIMENSIONS = 14


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Dimension(BaseModel):
    index: int
    label: str
    unit: str = ""
    min: float = 0.0
    max: float = 1.0


class Constraint(BaseModel):
    id: str = Field(default_factory=_uid)
    label: str
    coeffs: List[float] = Field(min_length=DIMENSIONS, max_length=DIMENSIONS)
    b: float


class Profile(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    description: str = ""
    dimensions: List[Dimension] = Field(min_length=DIMENSIONS, max_length=DIMENSIONS)
    constraints: List[Constraint]
    # Nominal operating point, used for the margin readout (slack of each facet here).
    center: List[float] = Field(default_factory=lambda: [0.0] * DIMENSIONS)
    active: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[List[Dimension]] = None
    constraints: Optional[List[Constraint]] = None
    center: Optional[List[float]] = None


class MarginRow(BaseModel):
    constraint_id: str
    label: str
    slack: float  # b - a·center  (>0 = satisfied)
    normalized: float  # slack / ||a||  = euclidean distance to the hyperplane
    binding: bool
    violated: bool


class MarginReport(BaseModel):
    profile_id: str
    profile_name: str
    center: List[float]
    feasible: bool
    min_margin: float
    tightest: Optional[str] = None
    rows: List[MarginRow]


class ContainRequest(BaseModel):
    vector: List[float] = Field(min_length=DIMENSIONS, max_length=DIMENSIONS)
    source: str = "api"
    label: str = ""


class Event(BaseModel):
    id: str = Field(default_factory=_uid)
    profile_id: str
    profile_name: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    label: str = ""
    source: str = "api"
    vector: List[float]
    residuals: List[float]
    max_residual: float
    status: str  # "permitted" | "corrected" | "revised" | "withheld"
    mode: Optional[str] = None  # enforcement mode for gate events
    attempts: int = 1  # reflection attempts (gate events)
    projected_vector: Optional[List[float]] = None
    correction_magnitude: float = 0.0
    violated_constraints: List[str] = []
    latency_ms: float = 0.0
    iterations: int = 0
    created_at: datetime = Field(default_factory=_now)


class SimulateRequest(BaseModel):
    count: int = Field(default=6, ge=1, le=100)
    violation_probability: float = Field(default=0.35, ge=0.0, le=1.0)


class SimulateResult(BaseModel):
    generated: int
    corrected: int
    events: List[Event]


class HistogramBucket(BaseModel):
    label: str
    count: int


class TrendPoint(BaseModel):
    bucket: str
    total: int
    corrected: int


class ConstraintHit(BaseModel):
    label: str
    count: int


class ClientSplit(BaseModel):
    client_name: str
    permitted: int
    corrected: int


class TelemetrySummary(BaseModel):
    active_profile: Optional[str] = None
    active_profile_id: Optional[str] = None
    engine_status: str
    dimensions: int = DIMENSIONS
    constraint_count: int = 0
    total_events: int = 0
    permitted: int = 0
    corrected: int = 0
    withheld: int = 0
    revised: int = 0
    enforcement_mode: str = "projection"
    violation_rate: float = 0.0
    mean_correction: float = 0.0
    max_correction: float = 0.0
    mean_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    throughput_per_min: float = 0.0
    latency_histogram: List[HistogramBucket] = []
    violation_trend: List[TrendPoint] = []
    top_constraints: List[ConstraintHit] = []
    by_client: List[ClientSplit] = []
    enforce_api_keys: bool = False
    client_count: int = 0


class AuditEntry(BaseModel):
    id: str = Field(default_factory=_uid)
    action: str
    detail: str = ""
    actor: str = "operator"
    created_at: datetime = Field(default_factory=_now)
