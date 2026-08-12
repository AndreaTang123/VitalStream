"""SQLAlchemy ORM models mirroring the core data model (PRD 4.4).

Only the entities the api service owns directly (accounts, devices, generated
insights, audit log) live here. RawSignal/Feature/ConfigVersion are owned by
the ingestion/feature_extraction/config_service services and their own stores.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from vitalstream_common.schemas import DeviceStatus, Role

from api.db.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role"))
    created_at: Mapped[datetime] = mapped_column()

    devices: Mapped[list[DeviceORM]] = relationship(back_populates="user")


class DeviceORM(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    device_type: Mapped[str] = mapped_column(String)
    status: Mapped[DeviceStatus] = mapped_column(SAEnum(DeviceStatus, name="device_status"))

    user: Mapped[UserORM] = relationship(back_populates="devices")


class InsightORM(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    eval_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column()


class AuditLogORM(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    resource: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column()
