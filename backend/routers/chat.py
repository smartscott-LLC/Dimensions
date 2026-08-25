"""Coaching chat: a real LLM turn, gated by the polytope before anything is released.

The model reply is generated first, then run through lib/gatecore (the same core the
/gate console uses). In projection mode the reply is released with its corrected
vector; in refusal mode the reflection loop runs and a still-infeasible reply is
withheld. Every turn is persisted and logged as a telemetry event (source="chat").
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from lib import encoder, gatecore
from lib.db import db
from lib.ratelimit import check_rate_limit, resolve_limit
from models.chat import (
    ChatMessageRequest,
    ChatSession,
    ChatSessionCreate,
    ChatTurn,
)
from models.containment import Event, Profile
from models.gate import ENFORCEMENT_MODES
from routers.clients import get_settings_doc
from routers.containment import _active_profile, _profile_by_id, _resolve_client

router = APIRouter()

MODEL = os.environ.get("MODEL_NAME", "agnes-2.5-flash")
HISTORY_TURNS = 8

SYSTEM_PROMPT = (
    "You are the assistant behind a 14-dimensional geometric containment engine. Every "
    "reply you produce is encoded into a 14D vector over seven Plumb Line pairs "
    "(harmony/dominance, order/chaos, integrity/deception, flourishing/decline, "
    "relationships/isolation, boundaries/intrusion, grace/rigidity) and verified against a "
    "convex polytope Ax <= b before the operator ever sees it. Your job is to help the "
    "operator understand and configure that engine: explain facets, margins, projection vs "
    "refusal, and how prompt wording moves each axis. Be concrete and concise (under 180 "
    "words unless asked for more). Never claim certainty you do not have."
)


class ChatSessionList(BaseModel):
    sessions: List[ChatSession]


class ChatExport(BaseModel):
    session_id: str
    filename: str
    content: str  # markdown audit artifact
    turns: int


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    for key in ("created_at", "updated_at"):
        value = doc.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            doc[key] = value.replace(tzinfo=timezone.utc)
    return doc


async def _session_or_404(session_id: str) -> ChatSession:
    doc = await db.chat_sessions.find_one({"id": session_id})
    if not doc:
        raise HTTPException(status_code=404, detail="chat session not found")
    return ChatSession(**_clean(doc))


def _why(profile: Profile, labels: List[str]) -> List[str]:
    """Human-readable 'why it tripped' lines for each violated facet."""
    lines: List[str] = []
    by_label = {c.label: c for c in profile.constraints}
    for label in labels[:6]:
        constraint = by_label.get(label)
        if not constraint:
            lines.append(f"`{label}` was violated.")
            continue
        targets = sorted(set(encoder.revision_targets(constraint.coeffs)))
        names = ", ".join(encoder.DIMENSION_NAMES[t] for t in targets[:3]) or "—"
        lines.append(
            f"`{label}` breached — the wording needs more {names} to pull the vector back inside P."
        )
    return lines


async def _resolve_profile(client) -> Profile:
    if client and client.profile_id:
        pinned = await _profile_by_id(client.profile_id)
        if pinned:
            return pinned
    return await _active_profile()


@router.post("/chat/sessions", response_model=ChatSession)
async def create_session(
    payload: ChatSessionCreate,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> ChatSession:
    if payload.mode and payload.mode not in ENFORCEMENT_MODES:
        raise HTTPException(status_code=422, detail="mode must be projection|refusal")
    client = await _resolve_client(x_api_key)
    profile = await _resolve_profile(client)
    session = ChatSession(
        title=payload.title or "New session",
        client_id=client.id if client else None,
        client_name=client.name if client else None,
        profile_id=profile.id,
        profile_name=profile.name,
        mode=payload.mode,
        model=MODEL,
    )
    await db.chat_sessions.insert_one(session.model_dump())
    return session


@router.get("/chat/sessions", response_model=List[ChatSession])
async def list_sessions() -> List[ChatSession]:
    docs = await db.chat_sessions.find().sort("updated_at", -1).to_list(100)
    return [ChatSession(**_clean(d)) for d in docs]


@router.get("/chat/sessions/{session_id}/turns", response_model=List[ChatTurn])
async def list_turns(session_id: str) -> List[ChatTurn]:
    await _session_or_404(session_id)
    docs = await db.chat_turns.find({"session_id": session_id}).sort("created_at", 1).to_list(200)
    return [ChatTurn(**_clean(d)) for d in docs]


@router.get("/chat/sessions/{session_id}/export", response_model=ChatExport)
async def export_session(session_id: str) -> ChatExport:
    """Markdown audit artifact: every turn with its facet decision and reflection trace."""
    session = await _session_or_404(session_id)
    docs = await db.chat_turns.find({"session_id": session_id}).sort("created_at", 1).to_list(500)
    turns = [ChatTurn(**_clean(d)) for d in docs]

    lines: List[str] = [
        f"# Chat containment transcript — {session.title}",
        "",
        f"- session id: `{session.id}`",
        f"- polytope: {session.profile_name} (`{session.profile_id}`)",
        f"- attributed client: {session.client_name or 'unattributed'}",
        f"- model: {session.model}",
        f"- session mode: {session.mode or 'inherit'}",
        f"- turns: {session.turns} · withheld: {session.withheld}",
        f"- exported at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Verification is r = Ax − b, violated iff max(r) > 0.",
        "",
    ]
    for i, t in enumerate(turns, start=1):
        lines += [
            f"## Turn {i} — {t.decision.upper()} ({t.mode})",
            f"- event id: `{t.event_id}`  · timestamp: {t.created_at.isoformat()}",
            f"- max residual: {t.max_residual} · ‖Δx‖: {t.correction_magnitude}"
            f" · alignment: {t.alignment_score} · attempts: {t.attempts}",
            "",
            "**Operator**",
            "",
            f"> {t.user_text}",
            "",
            "**Model draft (pre-enforcement)**",
            "",
            f"> {t.draft_text}",
            "",
            "**Released**",
            "",
            f"> {t.released_text or '[WITHHELD — nothing released]'}",
            "",
        ]
        if t.violated_constraints:
            lines.append("**Facets violated**")
            lines.append("")
            lines += [f"- `{c}`" for c in t.violated_constraints]
            lines.append("")
        if t.why:
            lines.append("**Why it tripped**")
            lines.append("")
            lines += [f"- {w}" for w in t.why]
            lines.append("")
        if t.steps:
            lines.append("**Reflection trace**")
            lines.append("")
            for s in t.steps:
                lines.append(
                    f"- attempt {s.get('attempt')}: r_max {s.get('max_residual')} ·"
                    f" {'inside P' if s.get('feasible') else 'outside P'} · {s.get('note')}"
                )
            lines.append("")
        if t.withheld_reason:
            lines += [f"**Withheld reason:** {t.withheld_reason}", ""]
        if t.wisdom:
            lines.append("**Wisdom filter**")
            lines.append("")
            lines += [f"- {w}" for w in t.wisdom]
            lines.append("")
        lines.append("---")
        lines.append("")

    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session.title).strip("-")
    return ChatExport(
        session_id=session.id,
        filename=f"containment-transcript-{safe or 'session'}-{session.id[:8]}.md",
        content="\n".join(lines),
        turns=len(turns),
    )


async def _generate(
    session_id: str,
    history: List[ChatTurn],
    text: str,
    profile: Profile,
    mode: str,
    max_reflections: int,
) -> str:
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="MODEL_API_KEY is not configured")

    from openai import AsyncOpenAI

    base_url = os.environ.get("MODEL_API_URL", "https://api.openai.com/v1")
    client = AsyncOpenAI(api_key=key, base_url=base_url)

    facts = (
        f"\n\nLIVE ENGINE FACTS (authoritative — never contradict these):\n"
        f"- Active polytope: '{profile.name}' with {len(profile.constraints)} facets over 14 axes.\n"
        f"- Axis labels in order: "
        f"{', '.join(d.label for d in profile.dimensions)}.\n"
        f"- Enforcement mode for this session: {mode}.\n"
        f"- PROJECTION mode: an infeasible reply is silently corrected by Euclidean projection "
        f"onto P (Dykstra cyclic projection onto the half-spaces); the operator still receives text.\n"
        f"- REFUSAL mode: an infeasible reply enters a reflection loop — the draft is "
        f"deterministically rewritten and re-encoded up to {max_reflections} times; if it enters P "
        f"it is released as 'revised', otherwise it is WITHHELD and the operator receives nothing.\n"
        f"- Verification is r = Ax - b, violated iff max(r) > 0. Refusal does NOT set axes to "
        f"maximum values, and nothing about the engine uses a language model.\n"
    )

    # History is owned by us (Mongo), so it is replayed into the prompt each turn.
    transcript = ""
    for turn in history[-HISTORY_TURNS:]:
        released = turn.released_text or "[withheld by the containment engine]"
        transcript += f"Operator: {turn.user_text}\nYou: {released}\n"
    prompt = f"{transcript}Operator: {text}" if transcript else text

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + facts},
                {"role": "user", "content": prompt},
            ],
        )
        reply = (response.choices[0].message.content or "").strip()
    except Exception as exc:  # provider/network failure
        raise HTTPException(status_code=502, detail=f"model call failed: {exc}") from exc
    
    # Validate draft length to prevent memory issues from excessively long responses
    MAX_DRAFT_LENGTH = 8000
    if len(reply) > MAX_DRAFT_LENGTH:
        reply = reply[:MAX_DRAFT_LENGTH] + "...[truncated due to length]"
    
    return reply or "(the model returned an empty reply)"


@router.post("/chat/sessions/{session_id}/message", response_model=ChatTurn)
async def send_message(
    session_id: str,
    payload: ChatMessageRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> ChatTurn:
    session = await _session_or_404(session_id)
    client = await _resolve_client(x_api_key)
    settings = await get_settings_doc()

    client_id = client.id if client else session.client_id
    limit = resolve_limit(
        client.rate_limit_per_min if client else None,
        settings.rate_limit_default_per_min,
        settings.rate_limit_enabled,
    )
    allowed, usage, wait = await check_rate_limit(db, client_id, limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: {usage}/{limit} per minute",
            headers={"Retry-After": str(wait)},
        )

    mode, _source = gatecore.resolve_mode(
        session.mode,
        client.enforcement_mode if client else None,
        settings.enforcement_mode,
    )
    profile = await _resolve_profile(client)

    turn_docs = await db.chat_turns.find({"session_id": session_id}).sort("created_at", 1).to_list(200)
    history = [ChatTurn(**_clean(d)) for d in turn_docs]

    started = time.perf_counter()
    draft = await _generate(
        session_id, history, payload.text, profile, mode, settings.max_reflections
    )
    outcome = gatecore.evaluate(
        profile, draft, payload.text, mode, settings.max_reflections
    )
    latency_ms = (time.perf_counter() - started) * 1000.0

    event = Event(
        profile_id=profile.id,
        profile_name=profile.name,
        client_id=client.id if client else None,
        client_name=client.name if client else None,
        label=f"chat:{session.title[:40]}",
        source="chat",
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

    turn = ChatTurn(
        session_id=session_id,
        user_text=payload.text,
        draft_text=draft,
        released_text=outcome["final_text"] if outcome["decision"] != "withheld" else None,
        decision=outcome["decision"],
        mode=mode,
        encoded_vector=outcome["encoded"],
        final_vector=outcome["final_vector"],
        dimension_names=encoder.DIMENSION_NAMES,
        violated_constraints=outcome["violated_constraints"],
        why=_why(profile, outcome["violated_constraints"]),
        suggested_rewrite=outcome["suggested_rewrite"],
        max_residual=outcome["max_residual"],
        correction_magnitude=outcome["correction_magnitude"],
        alignment_score=outcome["alignment_score"],
        attempts=outcome["attempts"],
        steps=outcome["steps"],
        wisdom=outcome["wisdom"]["adjustments"],
        withheld_reason=outcome["withheld_reason"],
        latency_ms=round(latency_ms, 4),
        event_id=event.id,
    )
    await db.chat_turns.insert_one(turn.model_dump())
    await db.chat_sessions.update_one(
        {"id": session_id},
        {
            "$inc": {"turns": 1, "withheld": 1 if turn.decision == "withheld" else 0},
            "$set": {
                "updated_at": datetime.now(timezone.utc),
                "profile_id": profile.id,
                "profile_name": profile.name,
            },
        },
    )
    return turn
