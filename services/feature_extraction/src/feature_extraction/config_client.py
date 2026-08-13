"""Client for config_service: which feature-algo version applies to a device.

Implements the client side of gray release (PRD 3.1/4.2): each device is
deterministically bucketed 0-99 by its id, and routed to the canary version
if its bucket falls under the canary's rollout_pct, else the stable version.
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


class ConfigClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=5.0)

    async def resolve_algo_version(self, algo_name: str, device_id: UUID, default: str) -> str:
        """Resolve the gray-release-aware algo version, falling back to `default`.

        config_service's gray-release flow is a Week 3 deliverable (PRD
        milestones); feature_extraction shouldn't hard-fail in Week 1-2 just
        because that service isn't running yet.
        """
        try:
            response = await self._client.get(f"/api/v1/config/feature-algo/{algo_name}/active")
            response.raise_for_status()
        except httpx.HTTPError:
            logger.debug("config_service unavailable, using default algo_version=%s", default)
            return default

        active = response.json()  # {"stable": "v1", "canary": "v2", "rollout_pct": 10}
        if active.get("canary") and _bucket(device_id) < active.get("rollout_pct", 0):
            return active["canary"]
        return active["stable"]

    async def aclose(self) -> None:
        await self._client.aclose()


config_client = ConfigClient(base_url=settings.config_service_base_url)
