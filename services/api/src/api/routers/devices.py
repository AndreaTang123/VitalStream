from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vitalstream_common.schemas import DeviceStatus, Role

from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import CoachPatientORM, DeviceORM

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


class DeviceIn(BaseModel):
    device_type: str


class DeviceOut(BaseModel):
    id: str
    user_id: str
    device_type: str
    status: str
    bound_at: str


def _device_out(device: DeviceORM) -> DeviceOut:
    return DeviceOut(
        id=str(device.id),
        user_id=str(device.user_id),
        device_type=device.device_type,
        status=device.status.value if hasattr(device.status, "value") else device.status,
        bound_at=device.bound_at.isoformat(),
    )


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def bind_device(
    body: DeviceIn,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DeviceOut:
    if current_user.role != Role.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="only patients bind devices to themselves"
        )

    device = DeviceORM(
        user_id=current_user.id,
        device_type=body.device_type,
        status=DeviceStatus.ACTIVE,
        bound_at=datetime.now(UTC),
    )
    session.add(device)
    await session.commit()
    return _device_out(device)


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    current_user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> list[DeviceOut]:
    if current_user.role == Role.ADMIN:
        result = await session.execute(select(DeviceORM))
    elif current_user.role == Role.COACH:
        result = await session.execute(
            select(DeviceORM)
            .join(CoachPatientORM, CoachPatientORM.patient_id == DeviceORM.user_id)
            .where(CoachPatientORM.coach_id == current_user.id)
        )
    else:
        result = await session.execute(select(DeviceORM).where(DeviceORM.user_id == current_user.id))

    return [_device_out(d) for d in result.scalars().all()]
