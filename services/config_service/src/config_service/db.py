"""Postgres persistence for algo-version state + audit trail (PRD 3.1/4.2,
week3-layer1-deepening-guide.md Step 2/4).

Replaces the Week 0 scaffold's in-memory ConfigStore — version history needs
to survive a restart to actually be "version control" (Step 2), and the
audit table is the Week 3 seed for PRD 5.3's audit-log requirement (Week 6
reuses the same pattern for the full-stack layer's audit log).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AlgoVersionORM(Base):
    __tablename__ = "algo_versions"
    __table_args__ = (UniqueConstraint("algo_name", "version", name="uq_algo_versions_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    algo_name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # candidate / active / canary / retired
    rollout_pct: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlgoVersionAuditORM(Base):
    __tablename__ = "algo_version_audit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    algo_name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
