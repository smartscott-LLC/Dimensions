"""Containment engine API. Every route hangs off this router, mounted under /api."""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from lib.auth import current_user, require_admin
from lib.db import db
from lib.polytope import DIMENSIONS, euclidean, project, residuals, sample_vector
from lib.ratelimit import check_rate_limit, resolve_limit
from models.auth import User
from models.clients import Client, hash_key
from models.containment import (
    AuditEntry,
    ClientSplit,
    ConstraintHit,
    ContainRequest,
    Event,
    HistogramBucket,
    MarginReport,
    MarginRow,
    Profile,
    ProfileUpdate,
    SimulateRequest,
    SimulateResult,
    TelemetrySummary,
    TrendPoint,
)
from routers.clients import get_settings_doc

router = APIRouter()


def _aware(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    for key in ("created_at", "updated_at"):
        if key in doc:
            doc[key] = _aware(doc[key])
    return doc


async def _log_audit(action: str, detail: str) -> AuditEntry:
    entry = AuditEntry(action=action, detail=detail)
    await db.audit.insert_one(entry.model_dump())
    return entry


async def _active_profile() -> Profile:
    doc = await db.profiles.find_one({"active": True})
    if not doc:
        doc = await db.profiles.find_one({})
    if not doc:
        raise HTTPException(status_code=409, detail="no constraint profile configured")
    return Profile(**_clean(doc))


# ---------------------------------------------------------------- profiles


@router.get("/profiles", response_model=List[Profile])
async def list_profiles() -> List[Profile]:
    docs = await db.profiles.find().to_list(200)
    profiles = [Profile(**_clean(d)) for d in docs]
    profiles.sort(key=lambda p: (not p.active, p.name))
    return profiles


@router.get("/profiles/active", response_model=Profile)
async def get_active_profile() -> Profile:
    return await _active_profile()


@router.get("/profiles/{profile_id}", response_model=Profile)
async def get_profile(profile_id: str) -> Profile:
    doc = await db.profiles.find_one({"id": profile_id})
    if not doc:
        raise HTTPException(status_code=404, detail="profile not found")
    return Profile(**_clean(doc))


@router.post("/profiles", response_model=Profile)
async def create_profile(
    payload: Profile, _admin: User = Depends(require_admin)
) -> Profile:
    payload.active = False
    await db.profiles.insert_one(payload.model_dump())
    await _log_audit("profile.create", f"created profile '{payload.name}'")
    return payload


@router.put("/profiles/{profile_id}", response_model=Profile)
async def update_profile(
    profile_id: str, payload: ProfileUpdate, _admin: User = Depends(require_admin)
) -> Profile:
    doc = await db.profiles.find_one({"id": profile_id})
    if not doc:
        raise HTTPException(status_code=404, detail="profile not found")
    current = Profile(**_clean(doc))
    patch = payload.model_dump(exclude_none=True)
    changed = sorted(patch.keys())
    updated = current.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
    await db.profiles.replace_one({"id": profile_id}, updated.model_dump())
    await _log_audit(
        "profile.update",
        f"updated {', '.join(changed) or 'nothing'} on '{updated.name}'",
    )
    return updated


@router.post("/profiles/{profile_id}/activate", response_model=Profile)
async def activate_profile(
    profile_id: str, _admin: User = Depends(require_admin)
) -> Profile:
    doc = await db.profiles.find_one({"id": profile_id})
    if not doc:
        raise HTTPException(status_code=404, detail="profile not found")
    await db.profiles.update_many({}, {"$set": {"active": False}})
    await db.profiles.update_one({"id": profile_id}, {"$set": {"active": True}})
    profile = Profile(**_clean(await db.profiles.find_one({"id": profile_id})))
    await _log_audit("profile.activate", f"activated profile '{profile.name}'")
    return profile


# ---------------------------------------------------------------- containment


async def _profile_by_id(profile_id: str) -> Optional[Profile]:
    doc = await db.profiles.find_one({"id": profile_id})
    return Profile(**_clean(doc)) if doc else None


async def _resolve_client(api_key: Optional[str]) -> Optional[Client]:
    """Maps an X-API-Key header to its client. 401 on unknown/revoked keys, and on a
    missing key when enforcement is on."""
    settings = await get_settings_doc()

    if not api_key:
        if settings.enforce_api_keys:
            raise HTTPException(
                status_code=401, detail="API key required: send X-API-Key"
            )
        return None

    # Validate API key format: must be pk_ followed by 40 hex chars
    import re
    if not re.match(r'^pk_[0-9a-f]{40}$', api_key):
        raise HTTPException(status_code=401, detail="invalid API key format")

    doc = await db.clients.find_one({"key_hash": hash_key(api_key)})
    if not doc:
        raise HTTPException(status_code=401, detail="invalid API key")
    client = Client(**_clean(doc))
    if not client.active:
        raise HTTPException(status_code=401, detail="API key revoked")

    await db.clients.update_one(
        {"id": client.id}, {"$set": {"last_seen_at": datetime.now(timezone.utc)}}
    )
    return client


async def _evaluate(
    profile: Profile,
    vector: List[float],
    source: str,
    label: str,
    client: Optional[Client] = None,
) -> Event:
    rows = [c.coeffs for c in profile.constraints]
    thresholds = [c.b for c in profile.constraints]

    started = time.perf_counter()
    res = residuals(rows, thresholds, vector)
    max_residual = max(res) if res else 0.0
    violated = [profile.constraints[i].label for i, r in enumerate(res) if r > 1e-12]

    projected: Optional[List[float]] = None
    iterations = 0
    magnitude = 0.0
    if violated:
        projected, iterations = project(rows, thresholds, vector)
        magnitude = euclidean(vector, projected)
    latency_ms = (time.perf_counter() - started) * 1000.0

    event = Event(
        profile_id=profile.id,
        profile_name=profile.name,
        client_id=client.id if client else None,
        client_name=client.name if client else None,
        label=label,
        source=source,
        vector=[round(v, 6) for v in vector],
        residuals=[round(r, 6) for r in res],
        max_residual=round(max_residual, 6),
        status="corrected" if violated else "permitted",
        projected_vector=[round(v, 6) for v in projected] if projected else None,
        correction_magnitude=round(magnitude, 6),
        violated_constraints=violated,
        latency_ms=round(latency_ms, 4),
        iterations=iterations,
    )
    await db.events.insert_one(event.model_dump())
    return event


@router.post("/contain", response_model=Event)
async def contain(
    response: Response,
    payload: ContainRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Event:
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

    # A key may pin its own polytope, so a clinical model is never held to the bio profile.
    profile: Optional[Profile] = None
    if client and client.profile_id:
        profile = await _profile_by_id(client.profile_id)
    if profile is None:
        profile = await _active_profile()
    return await _evaluate(
        profile, payload.vector, payload.source or "api", payload.label, client
    )


@router.get("/profiles/{profile_id}/margins", response_model=MarginReport)
async def profile_margins(profile_id: str) -> MarginReport:
    """Slack of every facet at the profile's nominal centre — the lattice health readout."""
    doc = await db.profiles.find_one({"id": profile_id})
    if not doc:
        raise HTTPException(status_code=404, detail="profile not found")
    profile = Profile(**_clean(doc))

    center = profile.center or [0.0] * DIMENSIONS
    if len(center) < DIMENSIONS:
        center = list(center) + [0.0] * (DIMENSIONS - len(center))

    rows: List[MarginRow] = []
    for c in profile.constraints:
        reach = sum(c.coeffs[k] * center[k] for k in range(DIMENSIONS))
        slack = c.b - reach
        norm = sum(v * v for v in c.coeffs) ** 0.5
        rows.append(
            MarginRow(
                constraint_id=c.id,
                label=c.label,
                slack=round(slack, 6),
                normalized=round(slack / norm, 6) if norm > 0 else 0.0,
                binding=abs(slack) < 1e-9,
                violated=slack < -1e-9,
            )
        )

    tightest = min(rows, key=lambda r: r.normalized) if rows else None
    return MarginReport(
        profile_id=profile.id,
        profile_name=profile.name,
        center=center,
        feasible=all(not r.violated for r in rows),
        min_margin=round(tightest.normalized, 6) if tightest else 0.0,
        tightest=tightest.label if tightest else None,
        rows=rows,
    )


@router.post("/simulate", response_model=SimulateResult)
async def simulate(
    payload: SimulateRequest, _user: User = Depends(current_user)
) -> SimulateResult:
    fallback = await _active_profile()
    client_docs = await db.clients.find({"active": True}).to_list(50)
    clients = [Client(**_clean(d)) for d in client_docs]

    events: List[Event] = []
    for _ in range(payload.count):
        # Round-robin the synthetic load across registered clients so per-client
        # telemetry reflects real attribution, honouring each key's pinned polytope.
        client = random.choice(clients) if clients else None
        profile = fallback
        if client and client.profile_id:
            pinned = await _profile_by_id(client.profile_id)
            if pinned:
                profile = pinned

        rows = [c.coeffs for c in profile.constraints]
        thresholds = [c.b for c in profile.constraints]
        center = list(profile.center) or [d.min for d in profile.dimensions]

        breach = random.random() < payload.violation_probability
        vector = sample_vector(rows, thresholds, center, breach, random)

        events.append(
            await _evaluate(
                profile,
                vector,
                "simulator",
                f"synthetic-{random.randint(1000, 9999)}",
                client,
            )
        )
        if client:
            await db.clients.update_one(
                {"id": client.id}, {"$set": {"last_seen_at": datetime.now(timezone.utc)}}
            )
    corrected = sum(1 for e in events if e.status == "corrected")
    return SimulateResult(generated=len(events), corrected=corrected, events=events)


@router.get("/events", response_model=List[Event])
async def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    status: Optional[str] = None,
    source: Optional[str] = None,
    client_id: Optional[str] = None,
) -> List[Event]:
    query: Dict[str, Any] = {}
    if status in ("permitted", "corrected", "revised", "withheld"):
        query["status"] = status
    if source:
        query["source"] = source
    if client_id == "unattributed":
        query["client_id"] = None
    elif client_id:
        query["client_id"] = client_id
    docs = await db.events.find(query).sort("created_at", -1).to_list(limit)
    return [Event(**_clean(d)) for d in docs]


# ---------------------------------------------------------------- telemetry


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


@router.get("/telemetry/summary", response_model=TelemetrySummary)
async def telemetry_summary() -> TelemetrySummary:
    profile_doc = await db.profiles.find_one({"active": True}) or await db.profiles.find_one({})
    profile = Profile(**_clean(profile_doc)) if profile_doc else None

    docs = await db.events.find().sort("created_at", -1).to_list(2000)
    total = len(docs)
    corrected = sum(1 for d in docs if d.get("status") == "corrected")
    withheld = sum(1 for d in docs if d.get("status") == "withheld")
    revised = sum(1 for d in docs if d.get("status") == "revised")
    latencies = [float(d.get("latency_ms", 0.0)) for d in docs]
    corrections = [
        float(d.get("correction_magnitude", 0.0)) for d in docs if d.get("status") == "corrected"
    ]

    buckets = [
        ("<0.05 ms", 0.05),
        ("0.05-0.1 ms", 0.1),
        ("0.1-0.25 ms", 0.25),
        ("0.25-0.5 ms", 0.5),
        ("0.5-1 ms", 1.0),
        (">1 ms", float("inf")),
    ]
    counts = [0] * len(buckets)
    for value in latencies:
        for i, (_, upper) in enumerate(buckets):
            if value < upper:
                counts[i] += 1
                break

    now = datetime.now(timezone.utc)
    trend: List[TrendPoint] = []
    for step in range(11, -1, -1):
        start = now - timedelta(hours=step + 1)
        end = now - timedelta(hours=step)
        window = [d for d in docs if start <= _aware(d.get("created_at")) < end]
        trend.append(
            TrendPoint(
                bucket=end.strftime("%H:00"),
                total=len(window),
                corrected=sum(1 for d in window if d.get("status") == "corrected"),
            )
        )

    hits: Dict[str, int] = {}
    for d in docs:
        for label in d.get("violated_constraints", []) or []:
            hits[label] = hits.get(label, 0) + 1
    top = [
        ConstraintHit(label=k, count=v)
        for k, v in sorted(hits.items(), key=lambda kv: kv[1], reverse=True)[:6]
    ]

    recent = [d for d in docs if _aware(d.get("created_at")) >= now - timedelta(minutes=10)]

    splits: Dict[str, List[int]] = {}
    for d in docs:
        name = d.get("client_name") or "unattributed"
        entry = splits.setdefault(name, [0, 0])
        if d.get("status") == "corrected":
            entry[1] += 1
        else:
            entry[0] += 1
    by_client = [
        ClientSplit(client_name=name, permitted=vals[0], corrected=vals[1])
        for name, vals in sorted(
            splits.items(), key=lambda kv: kv[1][0] + kv[1][1], reverse=True
        )[:8]
    ]
    settings = await get_settings_doc()

    return TelemetrySummary(
        active_profile=profile.name if profile else None,
        active_profile_id=profile.id if profile else None,
        engine_status="nominal" if profile else "unconfigured",
        constraint_count=len(profile.constraints) if profile else 0,
        dimensions=DIMENSIONS,
        total_events=total,
        permitted=total - corrected - withheld - revised,
        corrected=corrected,
        withheld=withheld,
        revised=revised,
        enforcement_mode=settings.enforcement_mode,
        violation_rate=round((corrected / total) * 100, 2) if total else 0.0,
        mean_correction=round(sum(corrections) / len(corrections), 4) if corrections else 0.0,
        max_correction=round(max(corrections), 4) if corrections else 0.0,
        mean_latency_ms=round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
        p50_latency_ms=round(_percentile(latencies, 50), 4),
        p99_latency_ms=round(_percentile(latencies, 99), 4),
        throughput_per_min=round(len(recent) / 10.0, 2),
        latency_histogram=[
            HistogramBucket(label=buckets[i][0], count=counts[i]) for i in range(len(buckets))
        ],
        violation_trend=trend,
        top_constraints=top,
        by_client=by_client,
        enforce_api_keys=settings.enforce_api_keys,
        client_count=await db.clients.count_documents({"active": True}),
    )


@router.get("/audit", response_model=List[AuditEntry])
async def list_audit(limit: int = Query(default=50, ge=1, le=200)) -> List[AuditEntry]:
    docs = await db.audit.find().sort("created_at", -1).to_list(limit)
    return [AuditEntry(**_clean(d)) for d in docs]
