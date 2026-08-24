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

# Supabase configuration (optional)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWKS_URL = os.environ.get("SUPABASE_JWKS_URL", "")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")

# JWT denylist collection name
JWT_DENYLIST_COLLECTION = "jwt_denylist"

# Nonce collection for replay protection
NONCE_COLLECTION = "auth_nonces"
NONCE_EXPIRY_SECONDS = 300  # 5 minutes


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
    import uuid
    jti = str(uuid.uuid4())  # Unique token ID for revocation
    nbf = datetime.now(timezone.utc)  # Not before - now
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "exp": nbf + ttl,  # Expiration
        "nbf": nbf,  # Not before - prevents replay of old tokens
        "jti": jti,  # JWT ID for revocation tracking
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


async def revoke_token(token_jti: str, reason: str = "manual_revocation") -> None:
    """Add a token to the denylist for immediate revocation."""
    await db.jwt_denylist.insert_one({
        "jti": token_jti,
        "reason": reason,
        "revoked_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    })
    logger.info(f"Token {token_jti[:8]}... revoked: {reason}")


async def is_token_revoked(token_jti: str) -> bool:
    """Check if a token has been revoked."""
    if not token_jti:
        return False
    count = await db.jwt_denylist.count_documents({
        "jti": token_jti,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    return count > 0


async def cleanup_revoked_tokens() -> int:
    """Remove expired tokens from the denylist."""
    result = await db.jwt_denylist.delete_many({
        "expires_at": {"$lt": datetime.now(timezone.utc)}
    })
    return result.deleted_count


async def generate_nonce(user_id: str) -> str:
    """Generate a nonce for sensitive operations."""
    import secrets
    nonce = secrets.token_hex(16)
    await db.auth_nonces.insert_one({
        "nonce": nonce,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=NONCE_EXPIRY_SECONDS),
    })
    return nonce


async def validate_nonce(nonce: str, user_id: str) -> bool:
    """Validate and consume a nonce."""
    if not nonce or not user_id:
        return False
    
    count = await db.auth_nonces.count_documents({
        "nonce": nonce,
        "user_id": user_id,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    
    if count > 0:
        # Consume the nonce (single-use)
        await db.auth_nonces.delete_one({"nonce": nonce, "user_id": user_id})
        return True
    
    return False


async def cleanup_expired_nonces() -> int:
    """Remove expired nonces."""
    result = await db.auth_nonces.delete_many({
        "expires_at": {"$lt": datetime.now(timezone.utc)}
    })
    return result.deleted_count


async def verify_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Verify a Supabase JWT using JWKS."""
    if not SUPABASE_JWKS_URL or not SUPABASE_SECRET_KEY:
        return None
    
    try:
        import httpx
        from jose import jwt as jose_jwt, jwks
        
        # Fetch JWKS
        async with httpx.AsyncClient() as client:
            response = await client.get(SUPABASE_JWKS_URL)
            response.raise_for_status()
            jwks_data = response.json()
        
        # Get signing keys
        keys = jwks_data.get("keys", [])
        if not keys:
            return None
        
        # Verify token
        decoded = jose_jwt.decode(
            token,
            keys=keys,
            algorithms=["RS256"],
            audience="https://mvyhnfywnmbqixxtdpir.supabase.co/auth/v1/token",
        )
        return decoded
    except Exception as e:
        logger.warning(f"Supabase JWT verification failed: {e}")
        return None


async def current_user(
    authorization: Optional[str] = Header(default=None),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="sign in required")
    
    token = authorization.split(" ", 1)[1].strip()
    claims = None
    
    # Try custom JWT first
    try:
        claims = _decode(token)
        # Check if token is revoked
        if claims and claims.get("jti"):
            if await is_token_revoked(claims.get("jti")):
                raise HTTPException(status_code=401, detail="session revoked — sign in again")
    except HTTPException:
        raise
    except Exception:
        claims = None
    
    # Fall back to Supabase JWT if configured
    if not claims and SUPABASE_URL:
        supabase_claims = await verify_supabase_jwt(token)
        if supabase_claims:
            # Map Supabase claims to our format
            claims = {
                "sub": supabase_claims.get("sub"),
                "email": supabase_claims.get("email"),
                "role": supabase_claims.get("role", "operator"),
            }
    
    if not claims:
        raise HTTPException(status_code=401, detail="invalid session token")
    
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
