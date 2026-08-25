"""Console auth models (email + password, JWT). TS mirrors in frontend/src/lib/types.ts."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

ROLES = ("admin", "operator")


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_password_complexity(password: str) -> str:
    """Validate password meets complexity requirements."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if len(password) > 200:
        raise ValueError("Password must be at most 200 characters")
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r'[0-9]', password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[^A-Za-z0-9]', password):
        raise ValueError("Password must contain at least one special character")
    return password


class User(BaseModel):
    id: str = Field(default_factory=_uid)
    email: str
    name: str = ""
    role: str = "operator"  # admin | operator
    password_hash: str = Field(exclude=True)  # never serialised
    active: bool = True
    created_at: datetime = Field(default_factory=_now)
    last_login_at: Optional[datetime] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(default="", max_length=80)
    password: str = Field(min_length=12, max_length=200)
    role: str = "operator"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


class UserList(BaseModel):
    users: List[User]
