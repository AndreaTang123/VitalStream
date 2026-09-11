"""SQLAlchemy ORM models mirroring the core data model (PRD 4.4) plus the
Week 6/Layer 3 identity/RBAC/audit tables.

Only the entities the api service owns directly (accounts, devices, coach
grants, on-demand insights, audit log, refresh tokens) live here.
Feature/DeviceInsight rows are owned by feature_extraction/insight_service's
own stores (same physical Postgres, different service-managed tables) — api
reads them with raw SQL (see routers/features.py) rather than mapping them
into this Base, so Alembic here never thinks it owns another service's table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from vitalstream_common.schemas import DeviceStatus, Role

from api.db.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role"))
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    devices: Mapped[list[DeviceORM]] = relationship(back_populates="user")


class DeviceORM(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    device_type: Mapped[str] = mapped_column(String)
    status: Mapped[DeviceStatus] = mapped_column(SAEnum(DeviceStatus, name="device_status"))
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserORM] = relationship(back_populates="devices")


class CoachPatientORM(Base):
    """Resource-level RBAC grant: which patients a coach may access (PRD 5.3).

    Without this table, "coach can see patient data" degenerates into "coach
    can see everyone's data" — every coach-facing endpoint's authorization
    check joins through here.
    """

    __tablename__ = "coach_patient"

    coach_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class InsightORM(Base):
    """On-demand, user-triggered insights (`POST /insights/generate`).

    Distinct from insight_service's own `device_insights` table, which is
    the autonomous per-device pipeline's history — see
    insight_service/db.py's docstring for the split rationale.
    """

    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    eval_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefreshTokenORM(Base):
    """Lets a refresh token be revoked (logout) — plain JWTs can't be, since
    nothing about a stateless token can be invalidated before it expires."""

    __tablename__ = "refresh_tokens"

    jti: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLogORM(Base):
    """PRD 5.3: who (actor) did what (action) to whose data (target_user_id),
    when, and whether it was allowed. Only written for cross-user health data
    reads, config mutations, and auth events — see api/audit.py."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String, default="success")
    ip_address: Mapped[str | None] = mapped_column(INET().with_variant(String, "sqlite"), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
