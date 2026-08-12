"""In-memory config version store implementing validate → gray release → rollback (PRD 4.2).

A real deployment would back this with Postgres (see the `ConfigVersion` schema
in vitalstream_common) so version history survives restarts and is queryable
for the audit log. This in-memory version keeps the state machine explicit and
testable without a DB dependency.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import uuid4

from vitalstream_common.schemas import ConfigVersion, ConfigVersionStatus


class ConfigError(Exception):
    pass


@dataclass
class _AlgoState:
    stable: ConfigVersion
    canary: ConfigVersion | None = None


@dataclass
class ConfigStore:
    _algos: dict[str, _AlgoState] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get_active(self, algo_name: str) -> dict:
        state = self._algos.get(algo_name)
        if state is None:
            raise ConfigError(f"no config registered for algo '{algo_name}'")
        return {
            "stable": state.stable.version,
            "canary": state.canary.version if state.canary else None,
            "rollout_pct": state.canary.rollout_pct if state.canary else 0,
        }

    async def register_initial_stable(self, algo_name: str, version: str) -> ConfigVersion:
        async with self._lock:
            if algo_name in self._algos:
                raise ConfigError(f"algo '{algo_name}' already has a stable version")
            stable = ConfigVersion(
                id=uuid4(),
                algo_name=algo_name,
                version=version,
                status=ConfigVersionStatus.STABLE,
                rollout_pct=100,
            )
            self._algos[algo_name] = _AlgoState(stable=stable)
            return stable

    async def publish_canary(self, algo_name: str, version: str, rollout_pct: int) -> ConfigVersion:
        """Gray-release a new version alongside the current stable one."""
        if not 0 <= rollout_pct <= 100:
            raise ConfigError("rollout_pct must be between 0 and 100")

        async with self._lock:
            state = self._algos.get(algo_name)
            if state is None:
                raise ConfigError(f"no stable version registered for algo '{algo_name}' yet")

            canary = ConfigVersion(
                id=uuid4(),
                algo_name=algo_name,
                version=version,
                status=ConfigVersionStatus.CANARY,
                rollout_pct=rollout_pct,
            )
            state.canary = canary
            return canary

    async def promote_canary(self, algo_name: str) -> ConfigVersion:
        """Promote the current canary to stable (rollout_pct=100)."""
        async with self._lock:
            state = self._algos.get(algo_name)
            if state is None or state.canary is None:
                raise ConfigError(f"algo '{algo_name}' has no active canary to promote")

            promoted = state.canary.model_copy(
                update={"status": ConfigVersionStatus.STABLE, "rollout_pct": 100}
            )
            state.stable = promoted
            state.canary = None
            return promoted

    async def rollback(self, algo_name: str, version: str) -> ConfigVersion:
        """Roll back a canary version, leaving the previous stable version active."""
        async with self._lock:
            state = self._algos.get(algo_name)
            if state is None or state.canary is None or state.canary.version != version:
                raise ConfigError(f"version '{version}' is not the active canary for '{algo_name}'")

            rolled_back = state.canary.model_copy(update={"status": ConfigVersionStatus.ROLLED_BACK})
            state.canary = None
            return rolled_back


config_store = ConfigStore()
