from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import Role

from api.auth import CurrentUser
from api.db.base import get_db
from api.db.models import CoachPatientORM, DeviceORM, InsightORM, UserORM
from api.rbac import require_role

router = APIRouter(prefix="/api/v1/coach", tags=["coach"])


class LatestInsightOut(BaseModel):
    content: str
    created_at: str


class PatientOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    device_count: int
    latest_insight: LatestInsightOut | None


@router.get("/patients", response_model=list[PatientOut])
async def list_coach_patients(
    current_user: CurrentUser = Depends(require_role(Role.COACH, Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> list[PatientOut]:
    """week7 Step 7: the one backend addition the frontend guide called for
    — the frontend has nowhere else to get "which patients can this coach
    see" (coach_patient is otherwise only written to, never read back).
    `admin` gets every patient rather than an empty/grant-scoped list, since
    an admin isn't itself granted via coach_patient."""
    if current_user.role == Role.ADMIN:
        result = await session.execute(select(UserORM).where(UserORM.role == Role.PATIENT))
    else:
        result = await session.execute(
            select(UserORM)
            .join(CoachPatientORM, CoachPatientORM.patient_id == UserORM.id)
            .where(CoachPatientORM.coach_id == current_user.id)
        )
    patients = result.scalars().all()

    out: list[PatientOut] = []
    for patient in patients:
        device_count_result = await session.execute(
            select(func.count()).select_from(DeviceORM).where(DeviceORM.user_id == patient.id)
        )
        device_count = device_count_result.scalar_one()

        latest_result = await session.execute(
            select(InsightORM)
            .where(InsightORM.user_id == patient.id)
            .order_by(InsightORM.created_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()

        out.append(
            PatientOut(
                id=str(patient.id),
                email=patient.email,
                display_name=patient.display_name,
                device_count=device_count,
                latest_insight=(
                    LatestInsightOut(content=latest.content, created_at=latest.created_at.isoformat())
                    if latest is not None
                    else None
                ),
            )
        )
    return out


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
