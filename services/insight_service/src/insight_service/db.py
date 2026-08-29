"""Persistence for autonomously-generated DeviceInsight rows
(week4-layer2-milestone-guide.md Step 6).

Owned by insight_service itself (the Kafka consumer writes here directly),
distinct from api's `insights` table (InsightORM), which backs the
user-triggered on-demand endpoint. Redis (cache.py) is the *cache* — TTL'd,
existing purely to avoid repeat LLM calls; this table is the permanent
history Layer 3 will eventually show ("historical insights"), so it has no
expiry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Uuid
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from vitalstream_common.schemas import DeviceInsight


class Base(DeclarativeBase):
    pass


class DeviceInsightORM(Base):
    __tablename__ = "device_insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    insight_text: Mapped[str] = mapped_column(String)
    feature_snapshot: Mapped[dict] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    cache_hit: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[float] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)


class DeviceInsightStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def start(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def stop(self) -> None:
        await self._engine.dispose()

    async def insert(self, insight: DeviceInsight) -> None:
        async with self._session_factory() as session:
            session.add(
                DeviceInsightORM(
                    device_id=insight.device_id,
                    insight_text=insight.insight_text,
                    feature_snapshot=insight.feature_snapshot,
                    model=insight.model,
                    prompt_version=insight.prompt_version,
                    cache_hit=insight.cache_hit,
                    latency_ms=insight.latency_ms,
                    generated_at=datetime.fromtimestamp(insight.generated_at, tz=UTC),
                    prompt_tokens=insight.prompt_tokens,
                    completion_tokens=insight.completion_tokens,
                    cost_usd=insight.cost_usd,
                )
            )
            await session.commit()
