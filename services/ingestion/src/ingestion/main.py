"""Layer 1 ingestion service entrypoint (PRD 3.1 / 4.5).

Accepts batches of raw wearable waveform samples over HTTP and forwards them
to Kafka for downstream buffering and feature extraction. Runs under uvloop
for lower event-loop overhead.

WebSocket streaming is deliberately deferred (week1-2-layer1-guide.md): HTTP
POST is easier to test end-to-end first; a long-lived stream endpoint is a
Week 3+ addition once the batch path is proven.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from vitalstream_common.schemas import SignalBatch, SignalType
from vitalstream_common.telemetry import configure_tracing

from ingestion.device_registry import device_registry
from ingestion.kafka_producer import producer
from ingestion.security import verify_service_token

logger = logging.getLogger(__name__)

# week3-layer1-deepening-guide.md Step 5: configure the tracer before the app
# is instrumented, so the very first request already exports a span. The
# actual cross-process propagation (HTTP -> Kafka -> consume -> compute ->
# db write as ONE trace) happens in kafka_producer.py, which injects the
# current span's context into the outgoing Kafka message headers.
configure_tracing(service_name="ingestion")


class SignalBatchIn(BaseModel):
    signal_type: SignalType
    sample_rate_hz: float
    start_ts: float
    values: list[float]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # week3-layer1-deepening-guide.md Step 6: uvloop is easy to "install" and
    # have silently not take effect (e.g. a process manager overriding
    # --loop, or run.py not actually being the entrypoint used). Log the
    # concrete running loop class rather than trusting that a flag was set.
    loop_name = type(asyncio.get_running_loop()).__module__
    logger.info("ingestion running on event loop: %s", loop_name)
    await producer.start()
    await device_registry.start()
    yield
    await device_registry.stop()
    await producer.stop()


app = FastAPI(title="vitalstream-ingestion", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)


@app.post("/api/v1/devices/{device_id}/signals", status_code=202, dependencies=[Depends(verify_service_token)])
async def ingest_signal_batch(device_id: UUID, batch: SignalBatchIn) -> dict:
    # No audit log here even on rejection (week6 Step 7): this is the
    # highest-frequency path in the system, and device-auth failures belong
    # in metrics/monitoring, not the low-volume "who saw whose health data"
    # audit trail.
    if not device_registry.is_registered(device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="device_id is not a registered device"
        )
    await producer.send(SignalBatch(device_id=device_id, **batch.model_dump()))
    return {"accepted": len(batch.values)}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "event_loop": type(asyncio.get_running_loop()).__module__}
