"""Client for config_service: which feature-algo version applies to a device.

Implements the client side of gray release (PRD 3.1/4.2): each device is
deterministically bucketed 0-99 by its id, and routed to the canary version
if its bucket falls under the canary's rollout_pct, else the stable version.

fetch_active() is the only network call and is meant to be polled
periodically (week3-layer1-deepening-guide.md Step 3: every ~30s into an
in-memory cache) rather than awaited once per message — resolve_algo_version()
is a pure/sync function so the per-message hot path never blocks on I/O.
"""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

import httpx

from feature_extraction.settings import settings

logger = logging.getLogger(__name__)


def _bucket(device_id: UUID) -> int:
    digest = hashlib.sha256(str(device_id).encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


def resolve_algo_version(active: dict | None, device_id: UUID, default: str) -> str:
    """Resolve the gray-release-aware algo version from an already-fetched
    `active` config dict, falling back to `default` if none is cached yet
    (e.g. config_service was unreachable on every refresh so far)."""
    if not active:
        return default
    if active.get("canary") and _bucket(device_id) < active.get("rollout_pct", 0):
        return active["canary"]
    return active.get("stable") or default


class ConfigClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=5.0)

    async def fetch_active(self, algo_name: str) -> dict | None:
        """{"stable": "v1", "canary": "v2", "rollout_pct": 10}, or None if
        config_service is unreachable or has nothing registered for
        `algo_name` yet — callers should keep using their last-cached value
        (or a hardcoded default) rather than hard-failing on this."""
        try:
            response = await self._client.get(f"/api/v1/config/feature-algo/{algo_name}/active")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.debug("config_service fetch_active(%s) failed: %s", algo_name, exc)
            return None
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()


config_client = ConfigClient(base_url=settings.config_service_base_url)
