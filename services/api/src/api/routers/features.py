from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.audit import write_audit_log
from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import DeviceORM
from api.deps import authorize_device_access

router = APIRouter(prefix="/api/v1/features", tags=["features"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# `features` is owned/schema-managed by feature_extraction (feature_extraction/db.py),
# not by api's own Alembic migrations — same physical Postgres, different
# service's table, so this is a read-only raw-SQL query rather than an ORM
# mapping api's migrations would think it owns.
_FEATURES_QUERY = text(
    """
    SELECT feature_type, value, window, algo_version, window_end
    FROM features
    WHERE device_id = :device_id
      AND (:start_ts IS NULL OR window_end >= :start_ts)
      AND (:end_ts IS NULL OR window_end <= :end_ts)
    ORDER BY window_end DESC
    LIMIT :limit
    """
)


@router.get("/{device_id}")
async def get_device_features(
    device_id: UUID,
    request: Request,
    start_ts: str | None = Query(default=None, description="ISO timestamp lower bound"),
    end_ts: str | None = Query(default=None, description="ISO timestamp upper bound"),
    limit: int = Query(default=200, ge=1, le=2000),
    device: DeviceORM = Depends(authorize_device_access),
    actor: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await session.execute(
        _FEATURES_QUERY,
        {"device_id": str(device_id), "start_ts": start_ts, "end_ts": end_ts, "limit": limit},
    )
    rows = result.mappings().all()

    if actor.id != device.user_id:
        await write_audit_log(
            session,
            actor_id=actor.id,
            actor_email=actor.email,
            action="features.read",
            resource_type="device",
            resource_id=str(device_id),
            target_user_id=device.user_id,
            status="success",
            ip_address=_client_ip(request),
        )

    return [
        {
            "feature_type": row["feature_type"],
            "value": row["value"],
            "window": row["window"],
            "algo_version": row["algo_version"],
            "window_end": row["window_end"].isoformat(),
        }
        for row in rows
    ]
