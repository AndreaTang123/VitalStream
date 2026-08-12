"""Audit logging (PRD 3.3, 5.3): who accessed/changed what, when.

Called from routers for every sensitive access — viewing another user's health
data, publishing/rolling back a config version — per the PRD's "actor, time,
object" requirement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AuditLogORM


async def write_audit_log(session: AsyncSession, actor_id: UUID, action: str, resource: str) -> None:
    session.add(
        AuditLogORM(
            actor_id=actor_id,
            action=action,
            resource=resource,
            timestamp=datetime.now(UTC),
        )
    )
    await session.commit()
