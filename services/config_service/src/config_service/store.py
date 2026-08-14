"""Postgres-backed config store implementing validate -> gray release -> rollback
(PRD 4.2, week3-layer1-deepening-guide.md Step 2/4).

Each mutating call also appends a row to algo_version_audit in the same
transaction, so "who changed what, when" is queryable directly (PRD 5.3),
without a separate write path that could get out of sync.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from config_service.db import AlgoVersionAuditORM, AlgoVersionORM, Base


class ConfigError(Exception):
    pass


class ConfigStore:
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

    async def _get(self, session: AsyncSession, algo_name: str, version: str) -> AlgoVersionORM | None:
        result = await session.execute(
            select(AlgoVersionORM).where(
                AlgoVersionORM.algo_name == algo_name, AlgoVersionORM.version == version
            )
        )
        return result.scalar_one_or_none()

    async def _get_by_status(self, session: AsyncSession, algo_name: str, status: str) -> AlgoVersionORM | None:
        result = await session.execute(
            select(AlgoVersionORM).where(
                AlgoVersionORM.algo_name == algo_name, AlgoVersionORM.status == status
            )
        )
        return result.scalar_one_or_none()

    async def _audit(
        self, session: AsyncSession, algo_name: str, version: str, action: str, actor: str
    ) -> None:
        session.add(
            AlgoVersionAuditORM(
                algo_name=algo_name,
                version=version,
                action=action,
                actor=actor,
                timestamp=datetime.now(UTC),
            )
        )

    async def get_active(self, algo_name: str) -> dict:
        async with self._session_factory() as session:
            stable = await self._get_by_status(session, algo_name, "active")
            if stable is None:
                raise ConfigError(f"no config registered for algo '{algo_name}'")
            canary = await self._get_by_status(session, algo_name, "canary")
            return {
                "stable": stable.version,
                "canary": canary.version if canary else None,
                "rollout_pct": canary.rollout_pct if canary else 0,
            }

    async def register_initial_stable(self, algo_name: str, version: str, actor: str) -> dict:
        async with self._session_factory() as session:
            existing = await self._get_by_status(session, algo_name, "active")
            if existing is not None:
                raise ConfigError(f"algo '{algo_name}' already has a stable version")

            row = AlgoVersionORM(
                algo_name=algo_name,
                version=version,
                status="active",
                rollout_pct=100,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await self._audit(session, algo_name, version, "register_stable", actor)
            await session.commit()
            return {"algo_name": algo_name, "version": version, "status": row.status}

    async def publish_canary(self, algo_name: str, version: str, rollout_pct: int, actor: str) -> dict:
        """Gray-release a new version alongside the current stable one."""
        if not 0 <= rollout_pct <= 100:
            raise ConfigError("rollout_pct must be between 0 and 100")

        async with self._session_factory() as session:
            stable = await self._get_by_status(session, algo_name, "active")
            if stable is None:
                raise ConfigError(f"no stable version registered for algo '{algo_name}' yet")

            existing_canary = await self._get_by_status(session, algo_name, "canary")
            if existing_canary is not None:
                existing_canary.status = "retired"
                await self._audit(
                    session, algo_name, existing_canary.version, "superseded_by_new_canary", actor
                )

            row = await self._get(session, algo_name, version)
            if row is None:
                row = AlgoVersionORM(
                    algo_name=algo_name,
                    version=version,
                    status="canary",
                    rollout_pct=rollout_pct,
                    created_at=datetime.now(UTC),
                )
                session.add(row)
            else:
                row.status = "canary"
                row.rollout_pct = rollout_pct

            await self._audit(session, algo_name, version, f"publish_canary(pct={rollout_pct})", actor)
            await session.commit()
            return {"algo_name": algo_name, "version": version, "status": row.status, "rollout_pct": rollout_pct}

    async def promote_canary(self, algo_name: str, actor: str) -> dict:
        """Promote the current canary to active (rollout_pct=100); old active retires."""
        async with self._session_factory() as session:
            canary = await self._get_by_status(session, algo_name, "canary")
            if canary is None:
                raise ConfigError(f"algo '{algo_name}' has no active canary to promote")

            old_stable = await self._get_by_status(session, algo_name, "active")
            if old_stable is not None:
                old_stable.status = "retired"
                await self._audit(session, algo_name, old_stable.version, "retired_on_promote", actor)

            canary.status = "active"
            canary.rollout_pct = 100
            await self._audit(session, algo_name, canary.version, "promote", actor)
            await session.commit()
            return {"algo_name": algo_name, "version": canary.version, "status": canary.status}

    async def rollback(self, algo_name: str, version: str, actor: str) -> dict:
        """Retire `version`. If it was the active one, restore the most
        recently-retired prior version to active — this covers both "kill an
        in-flight canary" and "we already promoted a bad version, undo it"
        (week3-layer1-deepening-guide.md Step 4).
        """
        async with self._session_factory() as session:
            target = await self._get(session, algo_name, version)
            if target is None:
                raise ConfigError(f"version '{version}' not found for algo '{algo_name}'")
            if target.status == "retired":
                raise ConfigError(f"version '{version}' is already retired")

            was_active = target.status == "active"
            target.status = "retired"
            target.rollout_pct = 0
            await self._audit(session, algo_name, version, "rollback", actor)

            restored_version = None
            if was_active:
                result = await session.execute(
                    select(AlgoVersionORM)
                    .where(
                        AlgoVersionORM.algo_name == algo_name,
                        AlgoVersionORM.status == "retired",
                        AlgoVersionORM.id != target.id,
                    )
                    .order_by(AlgoVersionORM.created_at.desc())
                    .limit(1)
                )
                restored = result.scalar_one_or_none()
                if restored is not None:
                    restored.status = "active"
                    restored.rollout_pct = 100
                    restored_version = restored.version
                    await self._audit(session, algo_name, restored.version, "restored_by_rollback", actor)

            await session.commit()
            return {"rolled_back": version, "restored_active": restored_version}

    async def audit_log(self, algo_name: str) -> list[dict]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AlgoVersionAuditORM)
                .where(AlgoVersionAuditORM.algo_name == algo_name)
                .order_by(AlgoVersionAuditORM.timestamp.desc())
            )
            return [
                {
                    "version": row.version,
                    "action": row.action,
                    "actor": row.actor,
                    "timestamp": row.timestamp.isoformat(),
                }
                for row in result.scalars().all()
            ]
