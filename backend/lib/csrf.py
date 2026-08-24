"""CSRF protection for the console.

Since we use localStorage JWT (not cookies), CSRF is inherently prevented
because browsers don't send custom headers cross-origin. However, we add
defense-in-depth with explicit CSRF token validation for state-changing operations.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from lib.db import db

logger = logging.getLogger(__name__)

# CSRF token expiry
CSRF_TOKEN_EXPIRY_HOURS = 12
CSRF_COLLECTION = "csrf_tokens"


async def generate_csrf_token(user_id: str) -> str:
    """Generate a CSRF token for a user session."""
    token = secrets.token_hex(32)
    await db.csrf_tokens.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=CSRF_TOKEN_EXPIRY_HOURS),
    })
    return token


async def validate_csrf_token(token: str, user_id: str) -> bool:
    """Validate a CSRF token for a user."""
    if not token or not user_id:
        return False
    
    count = await db.csrf_tokens.count_documents({
        "token": token,
        "user_id": user_id,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    
    if count > 0:
        # Consume the token (single-use)
        await db.csrf_tokens.delete_one({"token": token, "user_id": user_id})
        return True
    
    return False


async def cleanup_expired_csrf_tokens() -> int:
    """Remove expired CSRF tokens."""
    result = await db.csrf_tokens.delete_many({
        "expires_at": {"$lt": datetime.now(timezone.utc)}
    })
    return result.deleted_count


async def get_csrf_token(request: Request, user_id: str) -> Optional[str]:
    """Extract CSRF token from request headers or cookies."""
    # Check custom header first
    token = request.headers.get("X-CSRF-Token")
    if token:
        return token
    
    # Check cookie
    cookie_name = "csrf_token"
    token = request.cookies.get(cookie_name)
    if token:
        return token
    
    return None
