from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import InsightORM

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/{user_id}/insights")
async def list_user_insights(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    # TODO: once a coach-patient assignment table exists, restrict coach access
    # to only their assigned patients instead of any patient.
    if current_user.role == Role.PATIENT and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="patients may only view their own insights"
        )

    result = await session.execute(
        select(InsightORM).where(InsightORM.user_id == user_id).order_by(InsightORM.created_at.desc())
    )
    insights = result.scalars().all()

    await write_audit_log(
        session, actor_id=current_user.id, action="view_insights", resource=f"user:{user_id}"
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
