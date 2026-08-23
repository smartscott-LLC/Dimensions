"""Sliding-window rate limiting for the containment API.

Every accepted /contain call writes an event, so the events collection is itself the
usage ledger — no separate counter to drift out of sync. Limits are resolved as
per-client override -> engine default, and can be disabled entirely.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

WINDOW_SECONDS = 60


def resolve_limit(
    client_override: Optional[int], engine_default: int, enabled: bool
) -> Optional[int]:
    """None means 'unlimited'. 0 means 'blocked'."""
    if not enabled:
        return None
    if client_override is not None:
        return client_override
    return engine_default


async def usage_in_window(db, client_id: Optional[str]) -> int:
    since = datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)
    query = {"created_at": {"$gte": since}}
    query["client_id"] = client_id  # None matches the unattributed bucket
    return await db.events.count_documents(query)


async def retry_after(db, client_id: Optional[str]) -> int:
    """Seconds until the oldest call in the window falls out of it."""
    since = datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)
    cursor = (
        db.events.find({"client_id": client_id, "created_at": {"$gte": since}})
        .sort("created_at", 1)
        .limit(1)
    )
    docs = await cursor.to_list(1)
    if not docs:
        return 1
    oldest = docs[0].get("created_at")
    if isinstance(oldest, datetime):
        if not oldest.tzinfo:
            oldest = oldest.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - oldest).total_seconds()
        return max(1, int(WINDOW_SECONDS - elapsed) + 1)
    return 1


async def check_rate_limit(
    db, client_id: Optional[str], limit: Optional[int]
) -> Tuple[bool, int, int]:
    """Returns (allowed, usage, retry_after_seconds)."""
    if limit is None:
        return True, await usage_in_window(db, client_id), 0
    usage = await usage_in_window(db, client_id)
    if usage < limit:
        return True, usage, 0
    return False, usage, await retry_after(db, client_id)
