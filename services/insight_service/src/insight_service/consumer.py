"""Layer 2 insight consumer (PRD 3.2): consumes features-extracted, generates
personalized insights via cache-or-LLM, and persists every result — hit or
miss — to Postgres (week4-layer2-milestone-guide.md Step 3/6).

This is the autonomous counterpart to main.py's on-demand HTTP endpoint:
triggered by feature_extraction's throttled stream rather than a logged-in
user, and self-persisting rather than relying on api to write the row.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import create_async_engine
from vitalstream_common.schemas import DeviceInsight, InsightRequest

from insight_service.cache import get_cached, make_cache_key, set_cached
from insight_service.db import DeviceInsightStore
from insight_service.llm_client import llm_client
from insight_service.settings import settings

logger = logging.getLogger(__name__)


class InsightConsumerWorker:
    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._store = DeviceInsightStore(create_async_engine(settings.postgres_dsn))

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            settings.features_extracted_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.consumer_group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self._consumer.start()
        await self._store.start()

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
        await self._store.stop()

    async def run_forever(self) -> None:
        assert self._consumer is not None
        async for message in self._consumer:
            request = InsightRequest.model_validate(message.value)
            await self.handle_request(request)

    async def handle_request(self, request: InsightRequest) -> DeviceInsight | None:
        """Returns the persisted DeviceInsight, or None if LLM generation
        failed on a cache miss (logged and skipped — week4-layer2-milestone
        -guide.md Step 5: "调用失败时不要让整个consumer挂掉")."""
        model = settings.llm_model_name
        prompt_version = settings.prompt_version
        key = make_cache_key(request.feature_snapshot, prompt_version, model)

        start = time.monotonic()
        cached = await get_cached(key)

        if cached is not None:
            insight = DeviceInsight(
                device_id=request.device_id,
                insight_text=cached.insight_text,
                feature_snapshot=request.feature_snapshot,
                model=model,
                prompt_version=prompt_version,
                cache_hit=True,
                latency_ms=(time.monotonic() - start) * 1000,
                generated_at=time.time(),
            )
            logger.info("cache hit for %s (%.1fms)", request.device_id, insight.latency_ms)
        else:
            try:
                response = await llm_client.generate_device_insight(
                    request.feature_snapshot, prompt_version=prompt_version, model_version=model
                )
            except Exception as exc:  # noqa: BLE001 - any LLM failure: log and skip, don't crash the consumer
                logger.error("LLM generation failed for %s, skipping: %s", request.device_id, exc)
                return None

            insight = DeviceInsight(
                device_id=request.device_id,
                insight_text=response.content,
                feature_snapshot=request.feature_snapshot,
                model=response.model_version,
                prompt_version=response.prompt_version,
                cache_hit=False,
                latency_ms=response.latency_ms,
                generated_at=time.time(),
            )
            await set_cached(key, insight)
            logger.info(
                "generated insight for %s (%.1fms): %s",
                request.device_id,
                insight.latency_ms,
                insight.insight_text[:80],
            )

        await self._store.insert(insight)
        return insight


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = InsightConsumerWorker()
    await worker.start()
    try:
        await worker.run_forever()
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
