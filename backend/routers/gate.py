"""Dual-mode enforcement gate: deterministic text -> 14D -> containment -> decision.

Projection mode silently corrects an out-of-polytope draft. Refusal mode runs a
reflection loop (deterministic revision + re-encode) and withholds the response if
the draft is still outside P after `max_reflections` attempts. The decision core is
shared with the chat coach in lib/gatecore.py.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Response

from lib import encoder, gatecore
from lib.db import db
from lib.ratelimit import check_rate_limit, resolve_limit
from models.containment import Event, Profile
from models.gate import (
    ENFORCEMENT_MODES,
    EncodeRequest,
    EncodeResponse,
    GateRequest,
    GateResponse,
    ReflectionStep,
    WisdomReport,
)
from routers.clients import get_settings_doc
from routers.containment import _active_profile, _profile_by_id, _resolve_client

router = APIRouter()


@router.post("/encode", response_model=EncodeResponse)
async def encode_text(payload: EncodeRequest) -> EncodeResponse:
    """Deterministic text -> 14D ethical vector. No model call, no randomness."""
    return EncodeResponse(
        vector=encoder.encode(payload.text, payload.context),
        dimension_names=encoder.DIMENSION_NAMES,
    )


@router.post("/gate", response_model=GateResponse)
async def gate(
    response: Response,
    payload: GateRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> GateResponse:
    client = await _resolve_client(x_api_key)
    settings = await get_settings_doc()

    limit = resolve_limit(
        client.rate_limit_per_min if client else None,
        settings.rate_limit_default_per_min,
        settings.rate_limit_enabled,
    )
    allowed, usage, wait = await check_rate_limit(db, client.id if client else None, limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: {usage}/{limit} per minute",
            headers={"Retry-After": str(wait)},
        )
    if limit is not None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - usage - 1))

    if payload.mode and payload.mode not in ENFORCEMENT_MODES:
        raise HTTPException(status_code=422, detail="mode must be projection|refusal")
    mode, mode_source = gatecore.resolve_mode(
        payload.mode,
        client.enforcement_mode if client else None,
        settings.enforcement_mode,
    )
    max_reflections = payload.max_reflections or settings.max_reflections

    profile: Optional[Profile] = None
    if client and client.profile_id:
        profile = await _profile_by_id(client.profile_id)
    if profile is None:
        profile = await _active_profile()

    started = time.perf_counter()
    outcome = gatecore.evaluate(profile, payload.text, payload.context, mode, max_reflections)
    latency_ms = (time.perf_counter() - started) * 1000.0

    event = Event(
        profile_id=profile.id,
        profile_name=profile.name,
        client_id=client.id if client else None,
        client_name=client.name if client else None,
        label=payload.label or f"gate:{mode}",
        source="gate",
        vector=outcome["encoded"],
        residuals=outcome["residuals"],
        max_residual=outcome["max_residual"],
        status=outcome["decision"],
        projected_vector=outcome["final_vector"],
        correction_magnitude=outcome["correction_magnitude"],
        violated_constraints=outcome["violated_constraints"],
        latency_ms=round(latency_ms, 4),
        iterations=outcome["iterations"],
        mode=mode,
        attempts=outcome["attempts"],
    )
    await db.events.insert_one(event.model_dump())

    return GateResponse(
        decision=outcome["decision"],
        mode=mode,
        mode_source=mode_source,
        profile_id=profile.id,
        profile_name=profile.name,
        client_name=client.name if client else None,
        dimension_names=encoder.DIMENSION_NAMES,
        encoded_vector=outcome["encoded"],
        final_vector=outcome["final_vector"],
        final_text=outcome["final_text"],
        max_residual=outcome["max_residual"],
        correction_magnitude=outcome["correction_magnitude"],
        alignment_score=outcome["alignment_score"],
        violated_constraints=outcome["violated_constraints"],
        attempts=outcome["attempts"],
        iterations=outcome["iterations"],
        steps=[ReflectionStep(**s) for s in outcome["steps"]],
        wisdom=WisdomReport(**outcome["wisdom"]),
        latency_ms=round(latency_ms, 4),
        event_id=event.id,
        withheld_reason=outcome["withheld_reason"],
    )
