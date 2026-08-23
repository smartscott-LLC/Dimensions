"""Client / API-key management + per-client telemetry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import require_admin
from models.auth import User

from lib.db import db
from lib.ratelimit import resolve_limit, usage_in_window
from models.clients import (
    Client,
    ClientCreate,
    ClientCreated,
    ClientPatch,
    ClientStat,
    ClientStatsResponse,
    EngineSettings,
    EngineSettingsUpdate,
    mint_key,
)
from models.containment import AuditEntry

router = APIRouter()


def _aware(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    for key in ("created_at", "updated_at", "rotated_at", "last_seen_at"):
        if key in doc:
            doc[key] = _aware(doc[key])
    return doc


async def _log_audit(action: str, detail: str) -> None:
    await db.audit.insert_one(AuditEntry(action=action, detail=detail).model_dump())


async def _profile_name(profile_id: Optional[str]) -> Optional[str]:
    if not profile_id:
        return None
    doc = await db.profiles.find_one({"id": profile_id})
    return doc["name"] if doc else None


async def get_settings_doc() -> EngineSettings:
    doc = await db.settings.find_one({"id": "engine"})
    if not doc:
        fresh = EngineSettings()
        await db.settings.insert_one(fresh.model_dump())
        return fresh
    return EngineSettings(**_clean(doc))


@router.get("/settings", response_model=EngineSettings)
async def read_settings() -> EngineSettings:
    return await get_settings_doc()


@router.put("/settings", response_model=EngineSettings)
async def write_settings(
    payload: EngineSettingsUpdate, _admin: User = Depends(require_admin)
) -> EngineSettings:
    current = await get_settings_doc()
    if payload.enforcement_mode and payload.enforcement_mode not in ("projection", "refusal"):
        raise HTTPException(
            status_code=422, detail="enforcement_mode must be projection|refusal"
        )
    patch = payload.model_dump(exclude_none=True)
    updated = current.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    await db.settings.replace_one({"id": "engine"}, updated.model_dump(), upsert=True)

    notes = []
    if "enforce_api_keys" in patch:
        notes.append(
            f"API key enforcement {'enabled' if updated.enforce_api_keys else 'disabled'}"
        )
    if "rate_limit_enabled" in patch:
        notes.append(
            f"rate limiting {'enabled' if updated.rate_limit_enabled else 'disabled'}"
        )
    if "rate_limit_default_per_min" in patch:
        notes.append(f"default limit set to {updated.rate_limit_default_per_min}/min")
    if "enforcement_mode" in patch:
        notes.append(f"enforcement mode set to {updated.enforcement_mode}")
    if "max_reflections" in patch:
        notes.append(f"max reflections set to {updated.max_reflections}")
    if notes:
        await _log_audit("settings.update", "; ".join(notes))
    return updated


@router.patch("/clients/{client_id}", response_model=Client)
async def patch_client(
    client_id: str, payload: ClientPatch, _admin: User = Depends(require_admin)
) -> Client:
    doc = await db.clients.find_one({"id": client_id})
    if not doc:
        raise HTTPException(status_code=404, detail="client not found")

    updates: Dict[str, Any] = {}
    notes = []
    if payload.inherit_rate_limit:
        updates["rate_limit_per_min"] = None
        notes.append("rate limit reset to engine default")
    elif payload.rate_limit_per_min is not None:
        updates["rate_limit_per_min"] = payload.rate_limit_per_min
        notes.append(f"rate limit set to {payload.rate_limit_per_min}/min")

    if payload.inherit_enforcement_mode:
        updates["enforcement_mode"] = None
        notes.append("enforcement mode reset to engine default")
    elif payload.enforcement_mode:
        if payload.enforcement_mode not in ("projection", "refusal"):
            raise HTTPException(
                status_code=422, detail="enforcement_mode must be projection|refusal"
            )
        updates["enforcement_mode"] = payload.enforcement_mode
        notes.append(f"enforcement mode set to {payload.enforcement_mode}")

    if payload.clear_profile_pin:
        updates["profile_id"] = None
        updates["profile_name"] = None
        notes.append("profile pin cleared")
    elif payload.profile_id:
        if not await db.profiles.find_one({"id": payload.profile_id}):
            raise HTTPException(status_code=404, detail="pinned profile not found")
        updates["profile_id"] = payload.profile_id
        updates["profile_name"] = await _profile_name(payload.profile_id)
        notes.append(f"pinned to profile '{updates['profile_name']}'")

    if updates:
        await db.clients.update_one({"id": client_id}, {"$set": updates})
    client = Client(**_clean(await db.clients.find_one({"id": client_id})))
    if notes:
        await _log_audit("client.update", f"'{client.name}': {'; '.join(notes)}")
    return client


@router.get("/clients", response_model=List[Client])
async def list_clients() -> List[Client]:
    docs = await db.clients.find().to_list(200)
    clients = [Client(**_clean(d)) for d in docs]
    clients.sort(key=lambda c: (not c.active, c.name))
    return clients


@router.post("/clients", response_model=ClientCreated)
async def create_client(
    payload: ClientCreate, _admin: User = Depends(require_admin)
) -> ClientCreated:
    if payload.profile_id and not await db.profiles.find_one({"id": payload.profile_id}):
        raise HTTPException(status_code=404, detail="pinned profile not found")

    raw, prefix, hashed = mint_key()
    client = Client(
        name=payload.name,
        description=payload.description,
        key_prefix=prefix,
        key_hash=hashed,
        profile_id=payload.profile_id,
        profile_name=await _profile_name(payload.profile_id),
        rate_limit_per_min=payload.rate_limit_per_min,
    )
    doc = client.model_dump()
    doc["key_hash"] = hashed  # model_dump excludes it; persist explicitly
    await db.clients.insert_one(doc)
    await _log_audit("client.create", f"issued API key {prefix}… to '{client.name}'")
    return ClientCreated(client=client, api_key=raw)


@router.post("/clients/{client_id}/rotate", response_model=ClientCreated)
async def rotate_client_key(
    client_id: str, _admin: User = Depends(require_admin)
) -> ClientCreated:
    doc = await db.clients.find_one({"id": client_id})
    if not doc:
        raise HTTPException(status_code=404, detail="client not found")

    raw, prefix, hashed = mint_key()
    now = datetime.now(timezone.utc)
    await db.clients.update_one(
        {"id": client_id},
        {"$set": {"key_prefix": prefix, "key_hash": hashed, "rotated_at": now, "active": True}},
    )
    refreshed = Client(**_clean(await db.clients.find_one({"id": client_id})))
    await _log_audit("client.rotate", f"rotated key for '{refreshed.name}' -> {prefix}…")
    return ClientCreated(client=refreshed, api_key=raw)


@router.post("/clients/{client_id}/revoke", response_model=Client)
async def revoke_client(
    client_id: str, _admin: User = Depends(require_admin)
) -> Client:
    doc = await db.clients.find_one({"id": client_id})
    if not doc:
        raise HTTPException(status_code=404, detail="client not found")
    await db.clients.update_one({"id": client_id}, {"$set": {"active": False}})
    client = Client(**_clean(await db.clients.find_one({"id": client_id})))
    await _log_audit("client.revoke", f"revoked key {client.key_prefix}… for '{client.name}'")
    return client


@router.get("/clients/stats", response_model=ClientStatsResponse)
async def client_stats() -> ClientStatsResponse:
    clients = [Client(**_clean(d)) for d in await db.clients.find().to_list(200)]
    events = await db.events.find().sort("created_at", -1).to_list(3000)
    settings = await get_settings_doc()

    stats: List[ClientStat] = []
    for client in clients:
        mine = [e for e in events if e.get("client_id") == client.id]
        corrected = [e for e in mine if e.get("status") == "corrected"]
        latencies = sorted(float(e.get("latency_ms", 0.0)) for e in mine)
        mags = [float(e.get("correction_magnitude", 0.0)) for e in corrected]
        p99 = 0.0
        if latencies:
            idx = min(len(latencies) - 1, int(round(0.99 * (len(latencies) - 1))))
            p99 = latencies[idx]

        effective = resolve_limit(
            client.rate_limit_per_min,
            settings.rate_limit_default_per_min,
            settings.rate_limit_enabled,
        )
        usage = await usage_in_window(db, client.id)

        stats.append(
            ClientStat(
                client_id=client.id,
                client_name=client.name,
                key_prefix=client.key_prefix,
                active=client.active,
                profile_name=client.profile_name,
                calls=len(mine),
                corrected=len(corrected),
                violation_rate=round(len(corrected) / len(mine) * 100, 2) if mine else 0.0,
                mean_correction=round(sum(mags) / len(mags), 4) if mags else 0.0,
                p99_latency_ms=round(p99, 4),
                last_seen_at=client.last_seen_at,
                rate_limit_per_min=client.rate_limit_per_min,
                effective_limit=effective,
                enforcement_mode=client.enforcement_mode,
                effective_mode=client.enforcement_mode or settings.enforcement_mode,
                usage_last_min=usage,
                throttled=effective is not None and usage >= effective,
            )
        )

    stats.sort(key=lambda s: s.calls, reverse=True)
    unattributed = sum(1 for e in events if not e.get("client_id"))
    return ClientStatsResponse(stats=stats, unattributed_calls=unattributed)
