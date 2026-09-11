"""In-memory cache of registered device ids (PRD 4.5, week6 Step 7).

Rejects signal batches for a `device_id` nobody ever bound to an account via
`POST /api/v1/devices` (api service) — otherwise "binding a device" would be
purely decorative. Polled into memory on the same pattern as
feature_extraction's config_client cache: a periodic background refresh, not
a per-request query, so ingest's hot path never blocks on a DB round-trip.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from uuid import UUID

import asyncpg

from ingestion.config import settings

logger = logging.getLogger(__name__)


class DeviceRegistry:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None
        self._known: set[str] = set()
        self._refresh_task: asyncio.Task | None = None

    async def start(self) -> None:
        try:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=2)
        except OSError as exc:
            logger.warning("device_registry: could not connect to postgres yet: %s", exc)
            self._pool = None
        await self._refresh()
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task
        if self._pool is not None:
            await self._pool.close()

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(settings.device_registry_refresh_seconds)
            await self._refresh()

    async def _refresh(self) -> None:
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=2)
            except OSError:
                return
        try:
            rows = await self._pool.fetch("SELECT id FROM devices")
            self._known = {str(row["id"]) for row in rows}
        except asyncpg.PostgresError as exc:
            logger.warning("device_registry: refresh failed, keeping stale cache: %s", exc)

    def is_registered(self, device_id: UUID) -> bool:
        return str(device_id) in self._known


device_registry = DeviceRegistry(settings.postgres_dsn)
