from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.auth import CurrentUser
from api.db.base import get_db
from api.db.models import CoachPatientORM, UserORM
from api.rbac import require_role

router = APIRouter(prefix="/api/v1/coach", tags=["coach"])


class GrantIn(BaseModel):
    coach_id: UUID
    patient_id: UUID


@router.post("/patients", status_code=status.HTTP_201_CREATED)
async def grant_coach_access(
    body: GrantIn,
    current_user: CurrentUser = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> dict:
    for user_id, role in ((body.coach_id, Role.COACH), (body.patient_id, Role.PATIENT)):
        result = await session.execute(select(UserORM).where(UserORM.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.role != role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{user_id} is not a valid {role.value}"
            )

    existing = await session.execute(
        select(CoachPatientORM).where(
            CoachPatientORM.coach_id == body.coach_id, CoachPatientORM.patient_id == body.patient_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="grant already exists")

    session.add(
        CoachPatientORM(
            coach_id=body.coach_id,
            patient_id=body.patient_id,
            granted_at=datetime.now(UTC),
            granted_by=current_user.id,
        )
    )
    await session.commit()
    return {"coach_id": str(body.coach_id), "patient_id": str(body.patient_id)}
