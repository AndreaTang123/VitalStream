from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.audit import write_audit_log
from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import InsightORM
from api.settings import settings

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


class GenerateInsightIn(BaseModel):
    user_id: UUID
    features: dict[str, float]


@router.post("/generate")
async def generate_insight(
    body: GenerateInsightIn,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if current_user.role == Role.PATIENT and current_user.id != body.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="patients may only generate insights for themselves",
        )

    async with httpx.AsyncClient(base_url=settings.insight_service_base_url, timeout=30.0) as client:
        response = await client.post(
            "/api/v1/insights/generate",
            json={"user_id": str(body.user_id), "features": body.features},
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

    await write_audit_log(
        session, actor_id=current_user.id, action="generate_insight", resource=f"user:{body.user_id}"
    )

    return {
        "id": str(insight.id),
        "content": insight.content,
        "model_version": insight.model_version,
        "created_at": insight.created_at.isoformat(),
    }
