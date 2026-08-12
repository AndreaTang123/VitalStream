from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1/features", tags=["features"])


@router.get("/{device_id}")
async def get_device_features(
    device_id: UUID, current_user: CurrentUser = Depends(get_current_user)
) -> list[dict]:
    # TODO: feature_extraction currently only emits Feature messages onto Kafka
    # (see services/feature_extraction/src/feature_extraction/main.py) — it does
    # not yet persist them to TimescaleDB. Add that sink, then query it here.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="feature time-series query not implemented until feature_extraction writes to TimescaleDB",
    )
