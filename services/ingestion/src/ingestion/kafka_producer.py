"""Kafka producer wrapper (PRD 3.1: batch writes + connection reuse for throughput).

Wraps a single long-lived AIOKafkaProducer, tuned via `linger_ms`/`max_batch_size`
so the ingestion service coalesces bursts of signal writes instead of issuing one
round-trip per signal.
"""

from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer
from opentelemetry import propagate
from vitalstream_common.schemas import SignalBatch

from ingestion.config import settings

logger = logging.getLogger(__name__)


class SignalProducer:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            linger_ms=settings.kafka_linger_ms,
            max_batch_size=settings.kafka_max_batch_size_bytes,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()

    async def send(self, batch: SignalBatch) -> None:
        """Hand the batch to aiokafka's internal accumulator and return — do
        NOT await the broker ack here (that's what send_and_wait does, and
        benchmarking (week3-layer1-deepening-guide.md Step 1/6) showed it was
        forcing every HTTP response to block on a full produce round-trip,
        contradicting PRD 3.1's "写入成功立刻返回202，不要等下游处理完再返回").
        Delivery failures are still logged, just asynchronously.
        """
        if self._producer is None:
            raise RuntimeError("SignalProducer.start() must be called before send()")

        # week3-layer1-deepening-guide.md Step 5: inject the current span's
        # trace context into the Kafka message headers so feature_extraction
        # can continue the SAME trace on consume, instead of starting an
        # unrelated one.
        carrier: dict[str, str] = {}
        propagate.inject(carrier)
        headers = [(k, v.encode("utf-8")) for k, v in carrier.items()]

        future = await self._producer.send(
            settings.raw_signals_topic,
            value=batch.model_dump(mode="json"),
            key=str(batch.device_id).encode("utf-8"),
            headers=headers,
        )
        future.add_done_callback(_log_if_failed)


def _log_if_failed(future: asyncio.Future) -> None:
    exc = future.exception()
    if exc is not None:
        logger.error("failed to produce signal batch to Kafka: %s", exc)


producer = SignalProducer()
