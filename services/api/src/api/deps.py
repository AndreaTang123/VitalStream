"""Composable FastAPI dependencies for the two RBAC layers (PRD 3.3, 5.3):

- Role-level ("can this role call this endpoint at all"): `require_role` in
  api/rbac.py.
- Resource-level ("can this specific actor reach this specific user's/
  device's data"): `authorize_user_access` / `authorize_device_access` below.

Handlers depend on these instead of writing `if user.role == ...` inline —
permission checks scattered across handlers are exactly how an endpoint ends
up unintentionally unguarded (see tests/test_route_auth.py's route sweep).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import CoachPatientORM, DeviceORM


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _coach_has_grant(session: AsyncSession, coach_id: UUID, patient_id: UUID) -> bool:
    result = await session.execute(
        select(CoachPatientORM).where(
            CoachPatientORM.coach_id == coach_id, CoachPatientORM.patient_id == patient_id
        )
    )
    return result.scalar_one_or_none() is not None


async def _check_user_access(
    session: AsyncSession, actor: CurrentUser, target_user_id: UUID
) -> bool:
    """Pure predicate, no side effects — used by both the raising dependency
    below and by list-style endpoints (audit log, device list) that need to
    filter rather than 403 on the first mismatch."""
    if actor.role == Role.ADMIN:
        return True
    if actor.id == target_user_id:
        return True
    if actor.role == Role.COACH:
        return await _coach_has_grant(session, actor.id, target_user_id)
    return False


async def authorize_user_access(
    user_id: UUID,
    request: Request,
    actor: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """patient: only self. coach: only patients explicitly granted via
    coach_patient. admin: unrestricted. Denials are audited here (not left
    to the caller) since the raised exception short-circuits the handler.

    Parameter is named `user_id` (not `target_user_id`) so FastAPI binds it
    from a route's `{user_id}` path segment when used via `Depends()`.
    """
    allowed = await _check_user_access(session, actor, user_id)
    if not allowed:
        await write_audit_log(
            session,
            actor_id=actor.id,
            actor_email=actor.email,
            action="access.denied",
            resource_type="user",
            resource_id=str(user_id),
            target_user_id=user_id,
            status="denied",
            ip_address=_client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized for this user")
    return actor


async def authorize_device_access(
    device_id: UUID,
    request: Request,
    actor: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DeviceORM:
    """Resolves device_id -> owning user_id from the database (never from
    anything a caller could put in a token or query param), then applies the
    same ownership rule as authorize_user_access."""
    result = await session.execute(select(DeviceORM).where(DeviceORM.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")

    allowed = await _check_user_access(session, actor, device.user_id)
    if not allowed:
        await write_audit_log(
            session,
            actor_id=actor.id,
            actor_email=actor.email,
            action="access.denied",
            resource_type="device",
            resource_id=str(device_id),
            target_user_id=device.user_id,
            status="denied",
            ip_address=_client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not authorized for this device")
    return device
