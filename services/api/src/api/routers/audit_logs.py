from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.auth import CurrentUser
from api.db.base import get_db
from api.db.models import AuditLogORM
from api.rbac import require_role

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("")
async def list_audit_logs(
    _current_user: CurrentUser = Depends(require_role(Role.COACH, Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await session.execute(select(AuditLogORM).order_by(AuditLogORM.timestamp.desc()).limit(200))
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "actor_id": str(log.actor_id),
            "action": log.action,
            "resource": log.resource,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]
