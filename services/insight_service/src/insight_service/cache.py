"""Redis cache for LLM insight generations (PRD 3.2: avoid repeat-call cost/latency).

Cache key is a hash of everything that could change the output: the feature
values, the model version, and the prompt version — so an A/B test against a
different prompt version never serves a stale cached result from the other arm.
"""

from __future__ import annotations

import hashlib
import json

import redis.asyncio as redis
from vitalstream_common.schemas import DeviceInsight

from insight_service.settings import settings

_client = redis.from_url(settings.redis_url, decode_responses=True)


def cache_key(user_id: str, features: dict, model_version: str, prompt_version: str) -> str:
    payload = json.dumps(
        {"user_id": user_id, "features": features, "model": model_version, "prompt": prompt_version},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"insight:{digest}"


async def get_cached_insight(key: str) -> str | None:
    return await _client.get(key)


async def set_cached_insight(key: str, content: str) -> None:
    await _client.set(key, content, ex=settings.insight_cache_ttl_seconds)


# --- autonomous device-insight pipeline (week4-layer2-milestone-guide.md Step 4) ---
# Separate from cache_key() above: no device/user identity in the key at all
# (two devices with the same feature snapshot should share a cache entry —
# the generated text is generic lifestyle advice derived from numbers, not
# personalized to an identity), and normalized to fixed float precision so
# heart_rate_mean=72.001 vs 72.002 don't produce different keys.
_FLOAT_PRECISION = 2


def _round_floats(value):
    if isinstance(value, float):
        return round(value, _FLOAT_PRECISION)
    if isinstance(value, dict):
        return {k: _round_floats(v) for k, v in value.items()}
    return value


def make_cache_key(feature_snapshot: dict, prompt_version: str, model: str) -> str:
    normalized = _round_floats(feature_snapshot)
    payload = json.dumps(
        {"feature_snapshot": normalized, "prompt_version": prompt_version, "model": model},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"device_insight:{digest}"


async def get_cached(key: str) -> DeviceInsight | None:
    raw = await _client.get(key)
    if raw is None:
        return None
    return DeviceInsight.model_validate_json(raw)


async def set_cached(key: str, insight: DeviceInsight, ttl_seconds: int | None = None) -> None:
    ttl = ttl_seconds if ttl_seconds is not None else settings.insight_cache_ttl_seconds
    await _client.set(key, insight.model_dump_json(), ex=ttl)
