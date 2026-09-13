from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import DeviceORM, InsightORM
from api.settings import settings

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


class GenerateInsightIn(BaseModel):
    user_id: UUID
    device_id: UUID


# One row per feature_type: the most recent value seen for that device. Same
# `features` table as routers/features.py (feature_extraction-owned, raw SQL
# for the same reason — see that file's comment). Written as a portable
# correlated subquery (not Postgres' DISTINCT ON) so it's exercisable against
# the sqlite test database too.
_LATEST_FEATURES_QUERY = text(
    """
    SELECT f.feature_type, f.value
    FROM features f
    WHERE f.device_id = :device_id
      AND f.window_end = (
        SELECT MAX(f2.window_end) FROM features f2
        WHERE f2.device_id = f.device_id AND f2.feature_type = f.feature_type
      )
    """
)


@router.post("/generate")
async def generate_insight(
    body: GenerateInsightIn,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # PRD 4.5: only the patient themself, or an admin, can trigger generation
    # — unlike reads, this is not a coach-accessible action.
    if current_user.role == Role.COACH or (
        current_user.role == Role.PATIENT and current_user.id != body.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only the patient themself or an admin may generate insights",
        )

    device_result = await session.execute(select(DeviceORM).where(DeviceORM.id == body.device_id))
    device = device_result.scalar_one_or_none()
    if device is None or device.user_id != body.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found for this user")

    feature_rows = await session.execute(_LATEST_FEATURES_QUERY, {"device_id": str(body.device_id)})
    features = {row["feature_type"]: row["value"] for row in feature_rows.mappings().all()}
    if not features:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no feature data yet for this device — start the simulator and wait for a window to land",
        )

    # Synchronous, not published-to-Kafka-and-polled: this is the on-demand
    # path (week4-layer2-milestone-guide.md), which already reuses
    # insight_service's Redis cache, so a repeat click on an unchanged
    # feature snapshot is a cache hit (~ms), not a fresh LLM call. The
    # autonomous per-device pipeline (feature_extraction's throttled
    # publish -> insight_service.consumer -> device_insights) is the
    # Kafka-decoupled path; this button intentionally isn't it — see
    # README "前端架构" for why the frontend awaits this call directly
    # instead of polling a 202.
    async with httpx.AsyncClient(base_url=settings.insight_service_base_url, timeout=30.0) as client:
        response = await client.post(
            "/api/v1/insights/generate",
            json={"user_id": str(body.user_id), "features": features},
        )
    response.raise_for_status()
    generated = response.json()

    insight = InsightORM(
        user_id=body.user_id,
        content=generated["content"],
        model_version=generated["model_version"],
        eval_score=None,  # populated later by the eval/benchmark pipeline (PRD 6.2)
        created_at=datetime.now(UTC),
    )
    session.add(insight)
    await session.commit()

    if current_user.id != body.user_id:
        await write_audit_log(
            session,
            actor_id=current_user.id,
            actor_email=current_user.email,
            action="insights.generate",
            resource_type="user",
            resource_id=str(body.user_id),
            target_user_id=body.user_id,
            status="success",
        )

    return {
        "id": str(insight.id),
        "content": insight.content,
        "model_version": insight.model_version,
        "created_at": insight.created_at.isoformat(),
    }
