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
    """Raw wearable sensor channels (PRD 3.1: "原始信号窗口化处理为结构化特征").

    Distinct from `Feature.feature_type` (e.g. "heart_rate"), which is a
    *derived* metric computed from one or more of these raw channels.
    """

    PPG = "ppg"
    ECG = "ecg"
    ACC = "acc"
    EDA = "eda"


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


class SignalBatch(BaseModel):
    """A chunk of raw waveform samples from one device/channel (PRD 3.1/4.5 ingest contract).

    `start_ts` is the unix timestamp of `values[0]`; subsequent samples are
    spaced `1 / sample_rate_hz` seconds apart. Devices report in batches
    (e.g. one second of samples at a time) rather than one message per
    sample, so ingestion can do a single Kafka write per HTTP request.
    """

    device_id: UUID
    signal_type: SignalType
    sample_rate_hz: float
    start_ts: float
    values: list[float]


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
