"""Redis cache for LLM insight generations (PRD 3.2: avoid repeat-call cost/latency).

Cache key is a hash of everything that could change the output: the feature
values, the model version, and the prompt version — so an A/B test against a
different prompt version never serves a stale cached result from the other arm.
"""

from __future__ import annotations

import hashlib
import json

import redis.asyncio as redis

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
