"""Password hashing + JWT issue/verify + FastAPI auth dependencies.

The console (dashboard) is gated by these; the engine API (/contain, /gate, /chat) stays
on X-API-Key so machine clients are unaffected.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException

from lib.db import db
from models.auth import User

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12


def _secret() -> str:
    """Get JWT secret from environment. Raises if not configured."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is not set. "
            "This is required for production security. "
            "Please set JWT_SECRET in backend/.env before starting the server."
        )
    if secret == "dev-only-insecure-secret":
        raise RuntimeError(
            "JWT_SECRET is set to the default insecure value. "
            "Please generate a secure random secret and update backend/.env. "
            "Use: python -c 'import secrets; print(secrets.token_hex(32))'"
        )
    return secret


def validate_jwt_secret() -> None:
    """Validate that JWT_SECRET is properly configured at startup."""
    _secret()  # This will raise if not configured properly
    logger.info("JWT_SECRET is properly configured")


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except ValueError:
        return False


def issue_token(user: User) -> tuple[str, int]:
    ttl = timedelta(hours=TOKEN_TTL_HOURS)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + ttl,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM), int(ttl.total_seconds())


def _decode(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="session expired — sign in again")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid session token")


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    for key in ("created_at", "last_login_at"):
        value = doc.get(key)
        if isinstance(value, datetime) and value.tzinfo is None:
            doc[key] = value.replace(tzinfo=timezone.utc)
    return doc


async def current_user(
    authorization: Optional[str] = Header(default=None),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="sign in required")
    claims = _decode(authorization.split(" ", 1)[1].strip())
    doc = await db.users.find_one({"id": claims.get("sub")})
    if not doc:
        raise HTTPException(status_code=401, detail="account no longer exists")
    user = User(**_clean(doc))
    if not user.active:
        raise HTTPException(status_code=403, detail="account deactivated")
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin role required")
    return user


async def bootstrap_admin() -> None:
    """Seeds the single admin account on startup if the users collection is empty."""
    if await db.users.count_documents({}) > 0:
        return
    email = os.environ.get("ADMIN_EMAIL", "admin@polytope.console")
    password = os.environ.get("ADMIN_PASSWORD", "Prussian#42Blue")
    admin = User(
        email=email.lower(),
        name="Console Admin",
        role="admin",
        password_hash=hash_password(password),
    )
    doc = admin.model_dump()
    doc["password_hash"] = admin.password_hash  # excluded from model_dump
    await db.users.insert_one(doc)
