"""Kafka producer wrapper (PRD 3.1: batch writes + connection reuse for throughput).

Wraps a single long-lived AIOKafkaProducer, tuned via `linger_ms`/`kafka_batch_size`
so the ingestion service coalesces bursts of signal writes instead of issuing one
round-trip per signal.
"""

from __future__ import annotations

import json

from aiokafka import AIOKafkaProducer
from vitalstream_common.schemas import RawSignal

from ingestion.config import settings


class SignalProducer:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            linger_ms=settings.kafka_linger_ms,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()

    async def send(self, signal: RawSignal) -> None:
        if self._producer is None:
            raise RuntimeError("SignalProducer.start() must be called before send()")
        await self._producer.send_and_wait(
            settings.raw_signals_topic,
            value=signal.model_dump(mode="json"),
            key=str(signal.device_id).encode("utf-8"),
        )


producer = SignalProducer()
