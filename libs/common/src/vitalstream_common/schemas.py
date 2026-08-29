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
    """A user-requested, on-demand insight (PRD 4.5 `POST /insights/generate`,
    triggered via api's RBAC-gated endpoint and owned by api's own `insights`
    table). Distinct from `DeviceInsight` below, which is the Week 4
    milestone's *autonomous* background pipeline — same underlying LLM/cache
    machinery, different trigger (a logged-in user vs. a throttled stream of
    device feature windows) and different persisted owner."""

    id: UUID
    user_id: UUID
    content: str
    model_version: str
    eval_score: float | None = None
    created_at: datetime


class InsightRequest(BaseModel):
    """Published to the `features-extracted` topic once feature_extraction's
    per-device throttle allows it (week4-layer2-milestone-guide.md Step 2) —
    an aggregated snapshot over the last N windows, not a single Feature
    (too little signal to generate a non-generic insight from)."""

    device_id: UUID
    feature_snapshot: dict[str, float]
    window_start: float
    window_end: float


class DeviceInsight(BaseModel):
    """The autonomous counterpart to `Insight`: one row per InsightRequest
    processed by insight_service's Kafka consumer, cache_hit/latency_ms kept
    because they're the raw material for PRD 8's "cache hit rate -> cost/
    latency savings" metric, not just a debugging aid.

    prompt_tokens/completion_tokens/cost_usd (week5-layer2-deepening-guide.md
    Step 1/6) reflect the call that actually produced insight_text: on a
    cache miss, the real OpenAI usage + a static per-model price table; on a
    cache hit, 0 for all three — a hit produces no new LLM cost, and that's
    the point being measured (PRD 8's cache-savings metric)."""

    device_id: UUID
    insight_text: str
    feature_snapshot: dict[str, float]
    model: str
    prompt_version: str
    cache_hit: bool
    latency_ms: float
    generated_at: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class BenchmarkCase(BaseModel):
    """One hand-written case in the Layer 2 eval benchmark
    (week5-layer2-deepening-guide.md Step 2, benchmarks/cases.yaml).
    `checks` are natural-language checkpoints a human judged as necessary —
    not full expected-output text, since exact-match against LLM output
    isn't realistic. See eval/judge.py for how they're actually evaluated."""

    case_id: str
    feature_snapshot: dict[str, float]
    checks: list[str]
    category: str


class EvalResult(BaseModel):
    """One (case, prompt_version, model) run's outcome from
    evaluation/run_benchmark.py (week5-layer2-deepening-guide.md Step 4)."""

    case_id: str
    prompt_version: str
    model: str
    insight_text: str
    grounded: bool
    hallucination_flag: bool | None  # None: judge call failed, not scored — not the same as "no hallucination found"
    judge_notes: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class AuditLog(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    resource: str
    timestamp: datetime
