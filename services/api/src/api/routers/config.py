"""Proxies to config_service, gated to the platform-ops role (PRD 3.1/3.3)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import CurrentUser
from api.db.base import get_db
from api.rbac import require_role
from api.settings import settings

router = APIRouter(prefix="/api/v1/config/feature-algo", tags=["config"])


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
        response = await client.post("/api/v1/config/feature-algo", json=body.model_dump())
    response.raise_for_status()

    await write_audit_log(
        session,
        actor_id=current_user.id,
        action="publish_config_canary",
        resource=f"{body.algo_name}:{body.version}",
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
        response = await client.post(f"/api/v1/config/feature-algo/{algo_name}/{version}/rollback")
    response.raise_for_status()

    await write_audit_log(
        session,
        actor_id=current_user.id,
        action="rollback_config",
        resource=f"{algo_name}:{version}",
    )
    return response.json()
