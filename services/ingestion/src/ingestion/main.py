"""Layer 1 ingestion service entrypoint (PRD 3.1 / 4.5).

Accepts high-frequency wearable signals over HTTP (batch POST) and WebSocket
(continuous stream), and forwards them to Kafka for downstream buffering and
feature extraction. Runs under uvloop for lower event-loop overhead.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from vitalstream_common.schemas import RawSignal, SignalType

from ingestion.kafka_producer import producer


class SignalIn(BaseModel):
    signal_type: SignalType
    value: float
    timestamp: datetime


@asynccontextmanager
async def lifespan(_: FastAPI):
    await producer.start()
    yield
    await producer.stop()


app = FastAPI(title="vitalstream-ingestion", lifespan=lifespan)


@app.post("/api/v1/devices/{device_id}/signals")
async def ingest_signals(device_id: UUID, signals: list[SignalIn]) -> dict:
    for signal in signals:
        await producer.send(RawSignal(device_id=device_id, **signal.model_dump()))
    return {"accepted": len(signals)}


@app.websocket("/api/v1/devices/{device_id}/signals/stream")
async def ingest_signals_stream(websocket: WebSocket, device_id: UUID) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            signal_in = SignalIn.model_validate(payload)
            await producer.send(RawSignal(device_id=device_id, **signal_in.model_dump()))
    except Exception:
        await websocket.close()


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
