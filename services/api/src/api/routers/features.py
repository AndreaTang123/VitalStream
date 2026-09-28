from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import DateTime, Uuid, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.audit import write_audit_log
from api.auth import CurrentUser, get_current_user
from api.db.base import get_db
from api.db.models import DeviceORM
from api.deps import authorize_device_access

router = APIRouter(prefix="/api/v1/features", tags=["features"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _parse_iso(value: str | None, field_name: str) -> datetime | None:
    # Same asyncpg-needs-a-real-datetime issue as users.py's `before` cursor
    # — a raw ISO string bound against a timestamptz column works on sqlite
    # but not real Postgres.
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} must be an ISO 8601 timestamp"
        ) from exc


# `features` is owned/schema-managed by feature_extraction (feature_extraction/db.py),
# not by api's own Alembic migrations — same physical Postgres, different
# service's table, so this is a read-only raw-SQL query rather than an ORM
# mapping api's migrations would think it owns. `"window"` is quoted because
# it's a reserved word in Postgres (SQL:2003 window functions) — unquoted it
# was a syntax error ("syntax error at or near \"window\"") that sqlite,
# with no such reserved word, never caught.
_FEATURES_QUERY = text(
    """
    SELECT feature_type, value, "window", algo_version, window_end
    FROM features
    WHERE device_id = :device_id
      AND (:start_ts IS NULL OR window_end >= :start_ts)
      AND (:end_ts IS NULL OR window_end <= :end_ts)
    ORDER BY window_end DESC
    LIMIT :limit
    """
    # Explicit types for every param that can ever be NULL (or that's
    # compared against a Postgres-native `uuid` column) — asyncpg's prepare
    # step infers each parameter's type from the query, and gives up
    # ("could not determine data type of parameter") when the only context
    # is `:param IS NULL OR ...` and the value passed happens to be NULL
    # (the common case for end_ts, and start_ts on an unfiltered request).
    # sqlite's test DB never catches this — it doesn't type-check bind
    # params at prepare time the way a real Postgres connection does.
).bindparams(
    bindparam("device_id", type_=Uuid),
    bindparam("start_ts", type_=DateTime(timezone=True)),
    bindparam("end_ts", type_=DateTime(timezone=True)),
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
        {
            "device_id": device_id,
            "start_ts": _parse_iso(start_ts, "start_ts"),
            "end_ts": _parse_iso(end_ts, "end_ts"),
            "limit": limit,
        },
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
