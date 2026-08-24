"""Console authentication: email + password login, JWT sessions, operator management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from lib.auth import (
    current_user,
    hash_password,
    issue_token,
    require_admin,
    verify_password,
    _clean,
)
from lib.db import db
from models.auth import (
    ROLES,
    LoginRequest,
    PasswordChange,
    TokenResponse,
    User,
    UserCreate,
)
from models.containment import AuditEntry

logger = logging.getLogger(__name__)

router = APIRouter()

# Login rate limiting configuration
MAX_LOGIN_ATTEMPTS = 5  # IP-based rate limit
LOGIN_LOCKOUT_MINUTES = 15  # IP-based lockout duration

# Account lockout configuration
MAX_ACCOUNT_FAILURES = 5  # Consecutive failures before account lockout
ACCOUNT_LOCKOUT_HOURS = 1  # 1 hour lockout for accounts


async def _get_failed_attempts(ip: str) -> int:
    """Count failed login attempts from an IP in the last lockout window."""
    since = datetime.now(timezone.utc) - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    count = await db.login_attempts.count_documents({
        "ip": ip,
        "attempt_type": "failed",
        "created_at": {"$gte": since},
    })
    return count


async def _record_login_attempt(ip: str, success: bool, email: str = None) -> None:
    """Record a login attempt for rate limiting."""
    await db.login_attempts.insert_one({
        "ip": ip,
        "email": email,
        "attempt_type": "failed" if not success else "success",
        "created_at": datetime.now(timezone.utc),
    })


async def _cleanup_old_attempts() -> None:
    """Remove old login attempts to prevent unbounded growth."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    await db.login_attempts.delete_many(
        {"created_at": {"$lt": cutoff}}
    )


async def _get_consecutive_failures(email: str) -> int:
    """Count consecutive failed login attempts for an account."""
    # Get the last 10 attempts for this email to check consecutiveness
    recent = await db.login_attempts.find({
        "email": email,
        "attempt_type": {"$in": ["failed", "success"]},
    }).sort("created_at", -1).limit(10).to_list(None)
    
    consecutive = 0
    for attempt in recent:
        if attempt.get("attempt_type") == "failed":
            consecutive += 1
        else:
            # Reset on any success
            break
    return consecutive


async def _is_account_locked(email: str) -> bool:
    """Check if an account is currently locked out."""
    # Check for lockout record
    lockout = await db.account_lockouts.find_one({"email": email})
    if not lockout:
        return False
    
    # Check if lockout has expired
    lockout_until = lockout.get("lockout_until")
    if lockout_until and lockout_until > datetime.now(timezone.utc):
        return True
    
    # Lockout expired, remove it
    await db.account_lockouts.delete_one({"email": email})
    return False


async def _lock_account(email: str, hours: int = ACCOUNT_LOCKOUT_HOURS) -> None:
    """Lock an account for specified hours."""
    lockout_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    await db.account_lockouts.update_one(
        {"email": email},
        {"$set": {"email": email, "locked_at": datetime.now(timezone.utc), "lockout_until": lockout_until}},
        upsert=True
    )
    logger.warning(f"Account {email} locked out for {hours} hours due to {MAX_ACCOUNT_FAILURES} consecutive failures")


async def _log_audit(action: str, detail: str, actor: str) -> None:
    await db.audit.insert_one(
        AuditEntry(action=action, detail=detail, actor=actor).model_dump()
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
) -> TokenResponse:
    # Rate limiting check
    client_ip = request.client.host if request.client else "unknown"
    email = payload.email.lower()
    
    # Check if IP is locked out
    failed_count = await _get_failed_attempts(client_ip)
    if failed_count >= MAX_LOGIN_ATTEMPTS:
        # Calculate retry-after time
        retry_after = LOGIN_LOCKOUT_MINUTES * 60
        raise HTTPException(
            status_code=429,
            detail=f"too many failed attempts from this IP; retry after {retry_after} seconds",
            headers={"Retry-After": str(retry_after)},
        )
    
    # Check if account is locked out
    if await _is_account_locked(email):
        raise HTTPException(
            status_code=423,
            detail=f"account locked due to too many failed attempts; retry after 1 hour",
        )

    doc = await db.users.find_one({"email": email})
    if not doc or not verify_password(payload.password, doc.get("password_hash", "")):
        # Record failed attempt with email for account lockout tracking
        await _record_login_attempt(client_ip, success=False, email=email)
        
        # Check consecutive failures for account lockout
        consecutive_failures = await _get_consecutive_failures(email)
        if consecutive_failures >= MAX_ACCOUNT_FAILURES:
            await _lock_account(email)
            await _cleanup_old_attempts()
            raise HTTPException(
                status_code=423,
                detail=f"account locked due to {MAX_ACCOUNT_FAILURES} consecutive failed attempts",
            )
        
        # Cleanup old attempts periodically
        await _cleanup_old_attempts()
        raise HTTPException(status_code=401, detail="invalid email or password")
    
    # Record successful attempt and cleanup
    await _record_login_attempt(client_ip, success=True, email=email)
    await _cleanup_old_attempts()
    
    user = User(**_clean(doc))
    if not user.active:
        raise HTTPException(status_code=403, detail="account deactivated")

    now = datetime.now(timezone.utc)
    await db.users.update_one({"id": user.id}, {"$set": {"last_login_at": now}})
    user.last_login_at = now
    token, ttl = issue_token(user)
    return TokenResponse(access_token=token, expires_in=ttl, user=user)


@router.get("/auth/me", response_model=User)
async def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/auth/password", response_model=User)
async def change_password(
    payload: PasswordChange, user: User = Depends(current_user)
) -> User:
    doc = await db.users.find_one({"id": user.id})
    if not doc or not verify_password(payload.current_password, doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="current password is incorrect")
    await db.users.update_one(
        {"id": user.id}, {"$set": {"password_hash": hash_password(payload.new_password)}}
    )
    await _log_audit("user.password", f"password changed for {user.email}", user.email)
    return user


@router.get("/auth/users", response_model=List[User])
async def list_users(_: User = Depends(require_admin)) -> List[User]:
    docs = await db.users.find().sort("created_at", 1).to_list(200)
    return [User(**_clean(d)) for d in docs]


@router.post("/auth/users", response_model=User)
async def create_user(payload: UserCreate, admin: User = Depends(require_admin)) -> User:
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="role must be admin|operator")
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="an account with that email exists")

    user = User(
        email=email,
        name=payload.name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    doc = user.model_dump()
    doc["password_hash"] = user.password_hash
    await db.users.insert_one(doc)
    await _log_audit("user.create", f"created {user.role} account {email}", admin.email)
    return user


@router.post("/auth/users/{user_id}/toggle", response_model=User)
async def toggle_user(user_id: str, admin: User = Depends(require_admin)) -> User:
    doc = await db.users.find_one({"id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="account not found")
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="you cannot deactivate your own account")
    target = User(**_clean(doc))
    await db.users.update_one({"id": user_id}, {"$set": {"active": not target.active}})
    target.active = not target.active
    await _log_audit(
        "user.toggle",
        f"{'reactivated' if target.active else 'deactivated'} {target.email}",
        admin.email,
    )
    return target
