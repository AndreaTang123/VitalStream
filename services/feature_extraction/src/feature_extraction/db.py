"""Minimal persistence for extracted Feature rows (week1-2-layer1-guide.md Step 7).

Plain Postgres (not TimescaleDB — hypertables/continuous aggregates are a
Week 3+ optimization, not needed to make the pipeline's output queryable).
feature_extraction owns this table directly rather than going through the
`api` service's ORM, same as its existing config_service client.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Uuid
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from vitalstream_common.schemas import Feature


class Base(DeclarativeBase):
    pass


class FeatureORM(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    feature_type: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    window: Mapped[str] = mapped_column(String)
    algo_version: Mapped[str] = mapped_column(String)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class FeatureStore:
    def __init__(self, dsn: str) -> None:
        self._engine: AsyncEngine = create_async_engine(dsn, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def start(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def stop(self) -> None:
        await self._engine.dispose()

    async def insert(self, feature: Feature, window_end: datetime) -> None:
        async with self._session_factory() as session:
            session.add(
                FeatureORM(
                    device_id=feature.device_id,
                    feature_type=feature.feature_type,
                    value=feature.value,
                    window=feature.window,
                    algo_version=feature.algo_version,
                    window_end=window_end,
                )
            )
            await session.commit()
