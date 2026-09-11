"""Audit logging (PRD 3.3, 5.3): who accessed/changed what, when, and whether
it was allowed.

Only called for the things PRD 5.3 actually cares about — cross-user health
data reads, config mutations, auth events, and authorization denials — never
from a blanket middleware (see README "认证与权限" for why: a full request
log buries the "who looked at whose data" answer in health-check noise).

Written synchronously in the same request/transaction as the action it
records, not queued — these endpoints are low-frequency, and a dropped audit
row is a compliance problem in a way a dropped high-frequency data point
isn't (unlike the Kafka-decoupled data plane).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AuditLogORM


async def write_audit_log(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action: str,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    target_user_id: UUID | None = None,
    status: str = "success",
    ip_address: str | None = None,
    detail: dict | None = None,
    commit: bool = True,
) -> None:
    session.add(
        AuditLogORM(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            target_user_id=target_user_id,
            status=status,
            ip_address=ip_address,
            detail=detail,
            created_at=datetime.now(UTC),
        )
    )
    if commit:
        await session.commit()
