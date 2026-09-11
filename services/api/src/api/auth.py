"""OAuth2 / JWT authentication (PRD 3.3, 5.3).

`get_current_user` only decodes the JWT — it does not re-hit the database on
every request. That keeps auth cheap on the hot path, at the cost of a role
change not taking effect until the token expires and is reissued, which is an
acceptable tradeoff for a project this size (PRD non-goal: no HA/enterprise
session revocation). Refresh tokens are the exception: their `jti` is checked
against `refresh_tokens` on every use, so logout/revocation actually works.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from vitalstream_common.schemas import Role

from api.settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Same message for "no such user" and "wrong password" — distinguishing them
# lets an attacker enumerate registered emails (Step 3 security baseline).
INVALID_CREDENTIALS_DETAIL = "Incorrect email or password"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: UUID, role: Role, email: str = "") -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "email": email,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    # Algorithm is fixed at HS256 here AND pinned in the decode allowlist
    # below — never trust an `alg` a caller could influence (`alg: none`).
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@dataclass
class RefreshToken:
    jti: uuid.UUID
    user_id: UUID
    expires_at: datetime
    token: str


def create_refresh_token(user_id: UUID) -> RefreshToken:
    jti = uuid.uuid4()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
        "jti": str(jti),
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at, token=token)


def decode_refresh_token(token: str) -> tuple[UUID, uuid.UUID]:
    """Returns (user_id, jti). Raises HTTPException(401) on any decode/type issue."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise ValueError("not a refresh token")
        return UUID(payload["sub"]), uuid.UUID(payload["jti"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc


@dataclass
class CurrentUser:
    id: UUID
    role: Role
    email: str = ""


def _decode_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise ValueError("not an access token")
        return CurrentUser(
            id=UUID(payload["sub"]), role=Role(payload["role"]), email=payload.get("email", "")
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    return _decode_token(token)
