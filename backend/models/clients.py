"""Client (API key) models. TS mirrors live in frontend/src/lib/types.ts."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mint_key() -> tuple[str, str, str]:
    """Returns (plaintext_key, prefix_for_display, sha256_hash)."""
    raw = f"pk_{secrets.token_hex(20)}"
    return raw, raw[:11], hash_key(raw)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class Client(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    description: str = ""
    key_prefix: str
    key_hash: str = Field(exclude=True)  # never leaves the backend
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    # None = inherit the engine-wide default. 0 = block this client outright.
    rate_limit_per_min: Optional[int] = None
    # None = inherit the engine mode. "projection" | "refusal"
    enforcement_mode: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=_now)
    rotated_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    profile_id: Optional[str] = None
    rate_limit_per_min: Optional[int] = Field(default=None, ge=0, le=100000)


class ClientPatch(BaseModel):
    rate_limit_per_min: Optional[int] = Field(default=None, ge=0, le=100000)
    inherit_rate_limit: bool = False
    profile_id: Optional[str] = None
    clear_profile_pin: bool = False
    enforcement_mode: Optional[str] = None
    inherit_enforcement_mode: bool = False


class ClientCreated(BaseModel):
    client: Client
    api_key: str  # shown exactly once, at creation / rotation


class ClientStat(BaseModel):
    client_id: str
    client_name: str
    key_prefix: str
    active: bool
    profile_name: Optional[str] = None
    calls: int = 0
    corrected: int = 0
    violation_rate: float = 0.0
    mean_correction: float = 0.0
    p99_latency_ms: float = 0.0
    last_seen_at: Optional[datetime] = None
    rate_limit_per_min: Optional[int] = None
    effective_limit: Optional[int] = None
    enforcement_mode: Optional[str] = None
    effective_mode: str = "projection"
    usage_last_min: int = 0
    throttled: bool = False


class ClientViolation(BaseModel):
    client_name: str
    permitted: int
    corrected: int


class EngineSettings(BaseModel):
    id: str = "engine"
    enforce_api_keys: bool = False
    rate_limit_enabled: bool = False
    rate_limit_default_per_min: int = 120
    # "projection" = silently correct; "refusal" = reflection loop then withhold
    enforcement_mode: str = "projection"
    max_reflections: int = 3
    updated_at: datetime = Field(default_factory=_now)


class EngineSettingsUpdate(BaseModel):
    enforce_api_keys: Optional[bool] = None
    rate_limit_enabled: Optional[bool] = None
    rate_limit_default_per_min: Optional[int] = Field(default=None, ge=1, le=100000)
    enforcement_mode: Optional[str] = None
    max_reflections: Optional[int] = Field(default=None, ge=1, le=6)


class ClientStatsResponse(BaseModel):
    stats: List[ClientStat]
    unattributed_calls: int = 0
