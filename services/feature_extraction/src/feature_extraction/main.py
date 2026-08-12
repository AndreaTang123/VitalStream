"""Layer 1 feature extraction worker (PRD 3.1): consumes raw-signals, produces features.

Buffers a sliding window of raw values per (device, signal_type), and once a
window fills, extracts a feature using the algo version resolved for that
device via config_service (gray release), then emits a Feature message.

This is a skeleton: the windowing here is intentionally simple (fixed-size
buffer per device/signal, evaluated every N samples) rather than a real
time-based sliding window — replace with whatever windowing policy the real
feature set needs.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque

import numpy as np
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from vitalstream_common.schemas import Feature, RawSignal, SignalType

from feature_extraction.config_client import config_client
from feature_extraction.features import ALGO_VERSION_V1, resting_heart_rate
from feature_extraction.settings import settings

logger = logging.getLogger(__name__)

WINDOW_SIZE = 60

FEATURE_EXTRACTORS = {
    SignalType.HEART_RATE: ("resting_heart_rate", resting_heart_rate),
}


class FeatureExtractionWorker:
    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._buffers: dict[tuple[str, SignalType], deque[float]] = defaultdict(
            lambda: deque(maxlen=WINDOW_SIZE)
        )

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            settings.raw_signals_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.consumer_group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._consumer.start()
        await self._producer.start()

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
        if self._producer is not None:
            await self._producer.stop()
        await config_client.aclose()

    async def run_forever(self) -> None:
        assert self._consumer is not None and self._producer is not None
        async for message in self._consumer:
            signal = RawSignal.model_validate(message.value)
            await self._handle_signal(signal)

    async def _handle_signal(self, signal: RawSignal) -> None:
        extractor = FEATURE_EXTRACTORS.get(signal.signal_type)
        if extractor is None:
            return  # no feature defined for this signal type yet

        feature_type, extractor_fn = extractor
        buffer = self._buffers[(str(signal.device_id), signal.signal_type)]
        buffer.append(signal.value)
        if len(buffer) < buffer.maxlen:
            return

        algo_version = await config_client.resolve_algo_version(
            algo_name=feature_type, device_id=signal.device_id
        )
        value = extractor_fn(np.array(buffer))

        feature = Feature(
            device_id=signal.device_id,
            feature_type=feature_type,
            value=value,
            window=f"last_{WINDOW_SIZE}_samples",
            algo_version=algo_version or ALGO_VERSION_V1,
        )
        assert self._producer is not None
        await self._producer.send_and_wait(
            settings.features_topic,
            value=feature.model_dump(mode="json"),
            key=str(feature.device_id).encode("utf-8"),
        )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = FeatureExtractionWorker()
    await worker.start()
    try:
        await worker.run_forever()
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
