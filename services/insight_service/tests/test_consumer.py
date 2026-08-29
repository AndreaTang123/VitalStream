from uuid import uuid4

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from vitalstream_common.schemas import DeviceInsight, InsightRequest

from insight_service import consumer as consumer_module
from insight_service.consumer import InsightConsumerWorker
from insight_service.db import DeviceInsightORM, DeviceInsightStore
from insight_service.llm_client import LLMResponse


@pytest_asyncio.fixture
async def worker():
    # In-memory sqlite instead of the real Postgres DSN InsightConsumerWorker
    # builds with at construction time — StaticPool keeps every session on
    # the same connection (sqlite ":memory:" is otherwise per-connection).
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    store = DeviceInsightStore(engine)
    await store.start()

    w = InsightConsumerWorker()
    w._store = store
    yield w

    await store.stop()


def _request(**overrides) -> InsightRequest:
    defaults = dict(
        device_id=uuid4(),
        feature_snapshot={"heart_rate_mean": 72.0, "heart_rate_trend": 1.0, "window_count": 5.0},
        window_start=0.0,
        window_end=10.0,
    )
    defaults.update(overrides)
    return InsightRequest(**defaults)


async def _persisted_rows(worker):
    async with worker._store._session_factory() as session:
        result = await session.execute(select(DeviceInsightORM))
        return result.scalars().all()


async def test_cache_miss_calls_llm_persists_and_caches(worker, monkeypatch):
    llm_calls = []

    async def fake_generate(feature_snapshot, prompt_version=None, model_version=None):
        llm_calls.append(feature_snapshot)
        return LLMResponse(
            content="stay active!", model_version="gpt-4o-mini", prompt_version="v1",
            latency_ms=123.4, prompt_tokens=50, completion_tokens=20, cost_usd=0.0000195,
        )

    cache_store: dict[str, DeviceInsight] = {}

    async def fake_get_cached(key):
        return cache_store.get(key)

    async def fake_set_cached(key, insight, ttl_seconds=None):
        cache_store[key] = insight

    monkeypatch.setattr(consumer_module.llm_client, "generate_device_insight", fake_generate)
    monkeypatch.setattr(consumer_module, "get_cached", fake_get_cached)
    monkeypatch.setattr(consumer_module, "set_cached", fake_set_cached)

    insight = await worker.handle_request(_request())

    assert len(llm_calls) == 1
    assert insight.cache_hit is False
    assert insight.insight_text == "stay active!"
    assert len(cache_store) == 1

    rows = await _persisted_rows(worker)
    assert len(rows) == 1
    assert rows[0].cache_hit is False
    assert rows[0].insight_text == "stay active!"
    assert rows[0].prompt_tokens == 50
    assert rows[0].completion_tokens == 20
    assert rows[0].cost_usd > 0


async def test_cache_hit_skips_llm_but_still_persists(worker, monkeypatch):
    llm_calls = []

    async def fake_generate(*args, **kwargs):
        llm_calls.append(1)
        raise AssertionError("LLM should not be called on a cache hit")

    cached_insight = DeviceInsight(
        device_id=uuid4(),  # deliberately different device — cache key has no identity in it
        insight_text="previously generated tip",
        feature_snapshot={"heart_rate_mean": 72.0},
        model="gpt-4o-mini",
        prompt_version="v1",
        cache_hit=False,
        latency_ms=500.0,
        generated_at=0.0,
        prompt_tokens=50,
        completion_tokens=20,
        cost_usd=0.0000195,
    )

    async def fake_get_cached(key):
        return cached_insight

    set_cached_calls = []

    async def fake_set_cached(key, insight, ttl_seconds=None):
        set_cached_calls.append(insight)

    monkeypatch.setattr(consumer_module.llm_client, "generate_device_insight", fake_generate)
    monkeypatch.setattr(consumer_module, "get_cached", fake_get_cached)
    monkeypatch.setattr(consumer_module, "set_cached", fake_set_cached)

    insight = await worker.handle_request(_request())

    assert llm_calls == []
    assert set_cached_calls == []  # don't re-cache what's already cached
    assert insight.cache_hit is True
    assert insight.insight_text == "previously generated tip"
    assert insight.latency_ms < 500.0  # a cache lookup, not the original LLM call's latency

    rows = await _persisted_rows(worker)
    assert len(rows) == 1
    assert rows[0].cache_hit is True
    # a hit costs nothing new, regardless of what the original call cost
    assert rows[0].prompt_tokens == 0
    assert rows[0].completion_tokens == 0
    assert rows[0].cost_usd == 0.0


async def test_llm_failure_is_logged_and_skipped_not_raised(worker, monkeypatch):
    async def failing_generate(*args, **kwargs):
        raise TimeoutError("LLM call timed out")

    async def fake_get_cached(key):
        return None

    monkeypatch.setattr(consumer_module.llm_client, "generate_device_insight", failing_generate)
    monkeypatch.setattr(consumer_module, "get_cached", fake_get_cached)

    result = await worker.handle_request(_request())

    assert result is None
    assert await _persisted_rows(worker) == []
