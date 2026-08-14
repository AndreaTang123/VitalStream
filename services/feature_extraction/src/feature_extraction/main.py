"""Layer 1 feature extraction worker (PRD 3.1): consumes raw-signals, produces features.

Maintains a per-device sliding window buffer of raw PPG samples and, once
enough time has accumulated, runs the actual signal-processing pipeline
(bandpass filter + peak detection, see features.py) to derive heart rate —
rather than assuming an upstream device already computed it.

Windowing follows PPG-DaLiA's own convention (week1-2-layer1-guide.md Step
5): an 8-second window every 2-second step, so estimates line up with the
dataset's ground-truth labels for offline MAE validation (see
services/device_simulator/scripts/validate_against_ground_truth.py).

Only the PPG channel has a feature extractor wired up so far — ECG/ACC/EDA
are ingestible (SignalType) but unhandled here until a later week needs them.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import numpy as np
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from opentelemetry import propagate, trace
from vitalstream_common.schemas import Feature, SignalBatch, SignalType
from vitalstream_common.telemetry import configure_tracing

from feature_extraction.config_client import config_client, resolve_algo_version
from feature_extraction.db import FeatureStore
from feature_extraction.features import ALGO_VERSION_V1, HEART_RATE_ALGORITHMS
from feature_extraction.settings import settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

WINDOW_SECONDS = 8.0
STEP_SECONDS = 2.0
FEATURE_TYPE_HEART_RATE = "heart_rate"

# week3-layer1-deepening-guide.md Step 3: poll config_service into an
# in-memory cache instead of an HTTP round-trip per message.
CONFIG_REFRESH_INTERVAL_SECONDS = 30.0


@dataclass
class _DeviceBuffer:
    sample_rate_hz: float | None = None
    samples: deque[tuple[float, float]] = field(default_factory=deque)  # (timestamp, value)
    next_window_start: float | None = None


class FeatureExtractionWorker:
    def __init__(self) -> None:
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._store = FeatureStore(settings.postgres_dsn)
        self._buffers: dict[UUID, _DeviceBuffer] = defaultdict(_DeviceBuffer)
        self._active_config: dict | None = None
        self._config_refresh_task: asyncio.Task | None = None

    async def start(self) -> None:
        # Called here rather than at module import time so importing this
        # module (e.g. scripts/validate_ppg_dalia.py, for its WINDOW_SECONDS/
        # STEP_SECONDS constants) doesn't also spin up an OTLP exporter.
        configure_tracing(service_name="feature-extraction")

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
        await self._store.start()

        # Fetch once up front so the very first windows already have a real
        # config if config_service is up, then keep refreshing in the
        # background — the per-message hot path never awaits this.
        self._active_config = await config_client.fetch_active(FEATURE_TYPE_HEART_RATE)
        self._config_refresh_task = asyncio.create_task(self._refresh_config_loop())

    async def stop(self) -> None:
        if self._config_refresh_task is not None:
            self._config_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._config_refresh_task
        if self._consumer is not None:
            await self._consumer.stop()
        if self._producer is not None:
            await self._producer.stop()
        await self._store.stop()
        await config_client.aclose()

    async def _refresh_config_loop(self) -> None:
        while True:
            await asyncio.sleep(CONFIG_REFRESH_INTERVAL_SECONDS)
            active = await config_client.fetch_active(FEATURE_TYPE_HEART_RATE)
            if active is not None:
                self._active_config = active

    async def run_forever(self) -> None:
        assert self._consumer is not None
        async for message in self._consumer:
            batch = SignalBatch.model_validate(message.value)
            # week3-layer1-deepening-guide.md Step 5: continue the SAME trace
            # ingestion started (context was injected into these headers by
            # kafka_producer.py), rather than starting an unrelated one.
            carrier = {k: v.decode("utf-8") for k, v in (message.headers or [])}
            ctx = propagate.extract(carrier)
            with tracer.start_as_current_span("consume raw-signal", context=ctx):
                await self._handle_batch(batch)

    async def _handle_batch(self, batch: SignalBatch) -> None:
        if batch.signal_type != SignalType.PPG:
            return  # no feature extractor wired up for this channel yet

        buffer = self._buffers[batch.device_id]
        buffer.sample_rate_hz = batch.sample_rate_hz
        dt = 1.0 / batch.sample_rate_hz
        for i, value in enumerate(batch.values):
            buffer.samples.append((batch.start_ts + i * dt, value))

        if buffer.next_window_start is None:
            buffer.next_window_start = buffer.samples[0][0]

        while (
            buffer.samples
            and buffer.samples[-1][0] - buffer.next_window_start >= WINDOW_SECONDS
        ):
            await self._emit_window(batch.device_id, buffer)
            buffer.next_window_start += STEP_SECONDS
            while buffer.samples and buffer.samples[0][0] < buffer.next_window_start:
                buffer.samples.popleft()

    async def _emit_window(self, device_id: UUID, buffer: _DeviceBuffer) -> None:
        assert buffer.next_window_start is not None and buffer.sample_rate_hz is not None
        window_start = buffer.next_window_start
        window_end = window_start + WINDOW_SECONDS
        window_values = np.array(
            [value for ts, value in buffer.samples if window_start <= ts < window_end]
        )

        # Resolved from the cached config (no I/O here — see _refresh_config_loop)
        # so gray-release bucketing can't add per-message latency.
        algo_version = resolve_algo_version(self._active_config, device_id, default=ALGO_VERSION_V1)
        algo_fn = HEART_RATE_ALGORITHMS.get(algo_version, HEART_RATE_ALGORITHMS[ALGO_VERSION_V1])

        with tracer.start_as_current_span("compute feature (bandpass+peaks)") as span:
            span.set_attribute("algo_version", algo_version)
            try:
                bpm = algo_fn(window_values, buffer.sample_rate_hz)
            except ValueError as exc:
                logger.warning(
                    "skipping window [%.3f, %.3f) for %s: %s", window_start, window_end, device_id, exc
                )
                span.set_attribute("skipped", True)
                return

        feature = Feature(
            device_id=device_id,
            feature_type=FEATURE_TYPE_HEART_RATE,
            value=bpm,
            window=f"{window_start:.3f}-{window_end:.3f}",
            algo_version=algo_version,
        )
        logger.info("%s heart_rate=%.1f bpm (window ending %.3f)", device_id, bpm, window_end)

        assert self._producer is not None
        with tracer.start_as_current_span("produce features-topic"):
            await self._producer.send_and_wait(
                settings.features_topic,
                value=feature.model_dump(mode="json"),
                key=str(feature.device_id).encode("utf-8"),
            )
        with tracer.start_as_current_span("write features row (postgres)"):
            await self._store.insert(feature, window_end=datetime.fromtimestamp(window_end, tz=UTC))


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
