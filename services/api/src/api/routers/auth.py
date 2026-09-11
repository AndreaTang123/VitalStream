from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import (
    INVALID_CREDENTIALS_DETAIL,
    CurrentUser,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
)
from api.db.base import get_db
from api.db.models import RefreshTokenORM, UserORM
from api.rate_limit import check_login_rate_limit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    display_name: str | None
    is_active: bool


def _user_out(user: UserORM) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else user.role,
        display_name=user.display_name,
        is_active=user.is_active,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, session: AsyncSession = Depends(get_db)) -> UserOut:
    # Self-service registration only ever creates patients — coach/admin
    # accounts are created by an admin (POST /coach/patients-adjacent flows)
    # or scripts/seed.py, never by an anonymous caller.
    existing = await session.execute(select(UserORM).where(UserORM.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    user = UserORM(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=Role.PATIENT,
        display_name=body.display_name,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    await session.commit()
    return _user_out(user)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenOut)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TokenOut:
    if not check_login_rate_limit(form_data.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many login attempts, try again later"
        )

    result = await session.execute(select(UserORM).where(UserORM.email == form_data.username))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        await write_audit_log(
            session,
            actor_id=None,
            actor_email=form_data.username,
            action="auth.login_failed",
            status="denied",
            ip_address=_client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS_DETAIL)

    access_token = create_access_token(user.id, user.role, user.email)
    refresh = create_refresh_token(user.id)
    session.add(
        RefreshTokenORM(jti=refresh.jti, user_id=user.id, expires_at=refresh.expires_at, revoked_at=None)
    )
    await write_audit_log(
        session,
        actor_id=user.id,
        actor_email=user.email,
        action="auth.login_success",
        status="success",
        ip_address=_client_ip(request),
        commit=False,
    )
    await session.commit()

    return TokenOut(access_token=access_token, refresh_token=refresh.token)


class RefreshIn(BaseModel):
    refresh_token: str


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/refresh", response_model=AccessTokenOut)
async def refresh_access_token(body: RefreshIn, session: AsyncSession = Depends(get_db)) -> AccessTokenOut:
    user_id, jti = decode_refresh_token(body.refresh_token)

    result = await session.execute(select(RefreshTokenORM).where(RefreshTokenORM.jti == jti))
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked_at is not None or stored.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token revoked or unknown")

    user_result = await session.execute(select(UserORM).where(UserORM.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive")

    return AccessTokenOut(access_token=create_access_token(user.id, user.role, user.email))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshIn, session: AsyncSession = Depends(get_db)) -> None:
    _user_id, jti = decode_refresh_token(body.refresh_token)
    result = await session.execute(select(RefreshTokenORM).where(RefreshTokenORM.jti == jti))
    stored = result.scalar_one_or_none()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await session.commit()


@router.get("/me", response_model=UserOut)
async def read_me(
    current_user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> UserOut:
    result = await session.execute(select(UserORM).where(UserORM.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _user_out(user)
