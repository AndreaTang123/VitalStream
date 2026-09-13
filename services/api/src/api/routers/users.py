from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import DateTime, Uuid, bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.audit import write_audit_log
from api.auth import CurrentUser
from api.db.base import get_db
from api.db.models import InsightORM
from api.deps import authorize_user_access

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _parse_before(before: str | None) -> datetime | None:
    if before is None:
        return None
    # asyncpg binds parameters by Python type, not by casting from text —
    # comparing a DateTime column against a raw string works by accident on
    # sqlite (duck-typed) but fails against real Postgres, so parse it
    # explicitly rather than let the driver try.
    try:
        return datetime.fromisoformat(before)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="before must be an ISO 8601 timestamp"
        ) from exc


# `device_insights` is insight_service-owned (its own Base, same physical
# Postgres — see that service's db.py docstring for why it's a separate
# table from api's own `insights`): the autonomous per-device pipeline's
# history, joined here against api's own `devices` to scope it by user. Raw
# SQL for the same cross-service-table reason as routers/features.py.
_DEVICE_INSIGHTS_QUERY = text(
    """
    SELECT di.id, di.insight_text AS content, di.model AS model_version,
           di.prompt_version, di.cache_hit, di.cost_usd, di.generated_at AS created_at
    FROM device_insights di
    JOIN devices d ON d.id = di.device_id
    WHERE d.user_id = :user_id
      AND (:before IS NULL OR di.generated_at < :before)
    ORDER BY di.generated_at DESC
    LIMIT :limit
    """
    # `d.user_id` is api's own Uuid-typed ORM column (devices.user_id) — bind
    # it with an explicit Uuid type rather than a plain string so SQLAlchemy
    # encodes it correctly per-dialect (sqlite stores Uuid as 32-char hex,
    # Postgres as native uuid; a bare `str(user_id)` matches neither
    # reliably). `device_insights.device_id` is a different service's table
    # holding a real Postgres-native uuid in production, so it doesn't need
    # the same treatment there — this bindparam only has to get `user_id`
    # right.
).bindparams(bindparam("user_id", type_=Uuid)).columns(created_at=DateTime(timezone=True))


@router.get("/{user_id}/insights")
async def list_user_insights(
    user_id: UUID,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    before: str | None = Query(default=None, description="ISO timestamp cursor; return insights before this"),
    actor: CurrentUser = Depends(authorize_user_access),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    before_dt = _parse_before(before)

    # Merged from two sources — the on-demand `insights` table (this user's
    # own POST /insights/generate calls) and the autonomous
    # `device_insights` table (feature_extraction's throttled background
    # pipeline, for every device this user owns) — normalized to one shape
    # and merge-sorted in Python. A UNION-ing SQL query across an ORM table
    # and a raw cross-service table would work too, but at this project's
    # data volume (a demo user's insight history, not a fleet) two bounded
    # queries plus an in-memory sort is simpler to read and reason about.
    on_demand_stmt = select(InsightORM).where(InsightORM.user_id == user_id)
    if before_dt is not None:
        on_demand_stmt = on_demand_stmt.where(InsightORM.created_at < before_dt)
    on_demand_stmt = on_demand_stmt.order_by(InsightORM.created_at.desc()).limit(limit)

    on_demand_result = await session.execute(on_demand_stmt)
    on_demand_rows = [
        {
            "id": str(i.id),
            "content": i.content,
            "model_version": i.model_version,
            "prompt_version": None,
            "cache_hit": None,
            "cost_usd": None,
            "source": "on_demand",
            "created_at": i.created_at,
        }
        for i in on_demand_result.scalars().all()
    ]

    device_result = await session.execute(
        _DEVICE_INSIGHTS_QUERY, {"user_id": user_id, "before": before_dt, "limit": limit}
    )
    device_rows = [
        {
            "id": str(row["id"]),
            "content": row["content"],
            "model_version": row["model_version"],
            "prompt_version": row["prompt_version"],
            "cache_hit": row["cache_hit"],
            "cost_usd": row["cost_usd"],
            "source": "device",
            "created_at": row["created_at"],
        }
        for row in device_result.mappings().all()
    ]

    def _sort_key(row: dict) -> datetime:
        # sqlite's DateTime(timezone=True) coercion still comes back naive
        # (sqlite has no tz-aware storage at all) while InsightORM's
        # created_at round-trips as the aware value it was written with —
        # comparable in Postgres, not comparable in the sqlite test DB
        # without normalizing one side. Assume UTC for a naive value rather
        # than fail the comparison.
        value: datetime = row["created_at"]
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    merged = sorted(on_demand_rows + device_rows, key=_sort_key, reverse=True)[:limit]

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

    return [{**r, "created_at": r["created_at"].isoformat()} for r in merged]
