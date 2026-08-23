"""Console authentication: email + password login, JWT sessions, operator management."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException

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

router = APIRouter()


async def _log_audit(action: str, detail: str, actor: str) -> None:
    await db.audit.insert_one(
        AuditEntry(action=action, detail=detail, actor=actor).model_dump()
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_password(payload.password, doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="invalid email or password")
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
