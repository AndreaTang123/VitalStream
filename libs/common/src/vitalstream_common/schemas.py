"""Pydantic schemas for the core data model (PRD section 4.4).

These are the shared shapes passed between services (over Kafka, HTTP, and
persisted via each service's own ORM layer). Services may define their own
DB-mapped models (e.g. SQLAlchemy) that mirror these fields.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class Role(StrEnum):
    PATIENT = "patient"
    COACH = "coach"
    ADMIN = "admin"  # internal platform-ops role (PRD 1.3): config releases, audit log access


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SignalType(StrEnum):
    HEART_RATE = "heart_rate"
    HRV = "hrv"
    SLEEP = "sleep"
    ACTIVITY = "activity"


class ConfigVersionStatus(StrEnum):
    DRAFT = "draft"
    CANARY = "canary"
    STABLE = "stable"
    ROLLED_BACK = "rolled_back"


class User(BaseModel):
    id: UUID
    email: str
    role: Role
    created_at: datetime


class Device(BaseModel):
    id: UUID
    user_id: UUID
    device_type: str
    status: DeviceStatus


class RawSignal(BaseModel):
    device_id: UUID
    signal_type: SignalType
    value: float
    timestamp: datetime


class Feature(BaseModel):
    device_id: UUID
    feature_type: str
    value: float
    window: str
    algo_version: str


class ConfigVersion(BaseModel):
    id: UUID
    algo_name: str
    version: str
    status: ConfigVersionStatus
    rollout_pct: int = Field(ge=0, le=100)


class Insight(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    model_version: str
    eval_score: float | None = None
    created_at: datetime


class AuditLog(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    resource: str
    timestamp: datetime
