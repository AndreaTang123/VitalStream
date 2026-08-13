"""Layer 1 ingestion service entrypoint (PRD 3.1 / 4.5).

Accepts batches of raw wearable waveform samples over HTTP and forwards them
to Kafka for downstream buffering and feature extraction. Runs under uvloop
for lower event-loop overhead.

WebSocket streaming is deliberately deferred (week1-2-layer1-guide.md): HTTP
POST is easier to test end-to-end first; a long-lived stream endpoint is a
Week 3+ addition once the batch path is proven.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel
from vitalstream_common.schemas import SignalBatch, SignalType

from ingestion.kafka_producer import producer


class SignalBatchIn(BaseModel):
    signal_type: SignalType
    sample_rate_hz: float
    start_ts: float
    values: list[float]


@asynccontextmanager
async def lifespan(_: FastAPI):
    await producer.start()
    yield
    await producer.stop()


app = FastAPI(title="vitalstream-ingestion", lifespan=lifespan)


@app.post("/api/v1/devices/{device_id}/signals", status_code=202)
async def ingest_signal_batch(device_id: UUID, batch: SignalBatchIn) -> dict:
    await producer.send(SignalBatch(device_id=device_id, **batch.model_dump()))
    return {"accepted": len(batch.values)}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
