"""Proxies to config_service, gated to the platform-ops role (PRD 3.1/3.3)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import CurrentUser
from api.db.base import get_db
from api.rbac import require_role
from api.settings import settings

router = APIRouter(prefix="/api/v1/config/feature-algo", tags=["config"])


class RegisterStableIn(BaseModel):
    algo_name: str
    version: str


@router.get("/{algo_name}/versions")
async def list_versions(
    algo_name: str, current_user: CurrentUser = Depends(require_role(Role.ADMIN))
) -> list[dict]:
    # Read-only, admin-only — not audited (PRD 5.3's bar is sensitive
    # *mutations*/cross-user reads, and this is neither: it's the same
    # operator looking at their own config state).
    async with httpx.AsyncClient(base_url=settings.config_service_base_url, timeout=10.0) as client:
        response = await client.get(f"/api/v1/config/feature-algo/{algo_name}/versions")
    response.raise_for_status()
    return response.json()


@router.post("/register-stable")
async def register_stable(
    body: RegisterStableIn,
    current_user: CurrentUser = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> dict:
    async with httpx.AsyncClient(base_url=settings.config_service_base_url, timeout=10.0) as client:
        response = await client.post(
            "/api/v1/config/feature-algo/register-stable",
            json={**body.model_dump(), "actor": current_user.email},
        )
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail=response.json().get("detail"))
    response.raise_for_status()

    await write_audit_log(
        session,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="config.register_stable",
        resource_type="algo_version",
        resource_id=f"{body.algo_name}:{body.version}",
        status="success",
    )
    return response.json()


@router.post("/{algo_name}/promote")
async def promote(
    algo_name: str,
    current_user: CurrentUser = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> dict:
    async with httpx.AsyncClient(base_url=settings.config_service_base_url, timeout=10.0) as client:
        response = await client.post(
            f"/api/v1/config/feature-algo/{algo_name}/promote", json={"actor": current_user.email}
        )
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail=response.json().get("detail"))
    response.raise_for_status()

    await write_audit_log(
        session,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="config.promote",
        resource_type="algo_version",
        resource_id=algo_name,
        status="success",
    )
    return response.json()


class PublishCanaryIn(BaseModel):
    algo_name: str
    version: str
    rollout_pct: int = Field(ge=0, le=100)


@router.post("")
async def publish_canary(
    body: PublishCanaryIn,
    current_user: CurrentUser = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> dict:
    async with httpx.AsyncClient(base_url=settings.config_service_base_url, timeout=10.0) as client:
        response = await client.post(
            "/api/v1/config/feature-algo", json={**body.model_dump(), "actor": current_user.email}
        )
    response.raise_for_status()

    await write_audit_log(
        session,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="config.publish_canary",
        resource_type="algo_version",
        resource_id=f"{body.algo_name}:{body.version}",
        status="success",
        detail={"rollout_pct": body.rollout_pct},
    )
    return response.json()


@router.post("/{algo_name}/{version}/rollback")
async def rollback(
    algo_name: str,
    version: str,
    current_user: CurrentUser = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> dict:
    async with httpx.AsyncClient(base_url=settings.config_service_base_url, timeout=10.0) as client:
        response = await client.post(
            f"/api/v1/config/feature-algo/{algo_name}/{version}/rollback",
            json={"actor": current_user.email},
        )
    response.raise_for_status()

    await write_audit_log(
        session,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="config.rollback",
        resource_type="algo_version",
        resource_id=f"{algo_name}:{version}",
        status="success",
    )
    return response.json()
