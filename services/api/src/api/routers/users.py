from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.audit import write_audit_log
from api.auth import CurrentUser
from api.db.base import get_db
from api.db.models import InsightORM
from api.deps import authorize_user_access

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/{user_id}/insights")
async def list_user_insights(
    user_id: UUID,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    before: str | None = Query(default=None, description="ISO timestamp cursor; return insights before this"),
    actor: CurrentUser = Depends(authorize_user_access),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(InsightORM).where(InsightORM.user_id == user_id)
    if before is not None:
        stmt = stmt.where(InsightORM.created_at < before)
    stmt = stmt.order_by(InsightORM.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    insights = result.scalars().all()

    # Self-access isn't audited — only the cross-user case (coach/admin
    # reading someone else's data) is the "who looked at whose health data"
    # event PRD 5.3 cares about.
    if actor.id != user_id:
        await write_audit_log(
            session,
            actor_id=actor.id,
            actor_email=actor.email,
            action="insights.read",
            resource_type="user",
            resource_id=str(user_id),
            target_user_id=user_id,
            status="success",
            ip_address=_client_ip(request),
        )

    return [
        {
            "id": str(i.id),
            "content": i.content,
            "model_version": i.model_version,
            "eval_score": i.eval_score,
            "created_at": i.created_at.isoformat(),
        }
        for i in insights
    ]
