from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.auth import CurrentUser
from api.db.base import get_db
from api.db.models import AuditLogORM, CoachPatientORM
from api.rbac import require_role

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("")
async def list_audit_logs(
    actor_id: UUID | None = Query(default=None),
    target_user_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    since: str | None = Query(default=None, description="ISO timestamp lower bound"),
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: CurrentUser = Depends(require_role(Role.COACH, Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(AuditLogORM)

    if current_user.role == Role.COACH:
        # A coach's own audit-log view is scoped to what it's actually their
        # business to see: things they did, or reads/denials targeting a
        # patient they're granted for. Without this filter the "who can see
        # the audit log" question quietly becomes "everyone", which is the
        # canonical way an audit endpoint itself becomes the RBAC hole.
        granted = select(CoachPatientORM.patient_id).where(CoachPatientORM.coach_id == current_user.id)
        stmt = stmt.where(
            or_(AuditLogORM.actor_id == current_user.id, AuditLogORM.target_user_id.in_(granted))
        )

    if actor_id is not None:
        stmt = stmt.where(AuditLogORM.actor_id == actor_id)
    if target_user_id is not None:
        stmt = stmt.where(AuditLogORM.target_user_id == target_user_id)
    if action is not None:
        stmt = stmt.where(AuditLogORM.action == action)
    if since is not None:
        stmt = stmt.where(AuditLogORM.created_at >= since)

    stmt = stmt.order_by(AuditLogORM.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "actor_email": log.actor_email,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "target_user_id": str(log.target_user_id) if log.target_user_id else None,
            "status": log.status,
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "detail": log.detail,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
