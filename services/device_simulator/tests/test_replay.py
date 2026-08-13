from uuid import uuid4

import httpx
import numpy as np
import pytest

from device_simulator import replay
from device_simulator.ppg_dalia import default_data_dir


def test_default_data_dir_points_at_repo_data_raw():
    path = default_data_dir()
    assert path.parts[-3:] == ("data", "raw", "ppg_dalia") or path.name == "PPG_FieldStudy"
    assert str(path).endswith("data/raw/ppg_dalia/PPG_FieldStudy")


@pytest.mark.asyncio
async def test_replay_sends_one_batch_per_chunk(monkeypatch):
    fs = 64.0
    seconds = 3
    synthetic_bvp = np.arange(int(fs) * seconds, dtype=float)
    monkeypatch.setattr(replay, "load_wrist_bvp", lambda data_dir, subject: synthetic_bvp)

    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(202, json={"accepted": 64})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(replay.httpx, "AsyncClient", fake_async_client)

    await replay.replay(
        data_dir=default_data_dir(),
        subject="S2",
        device_id=uuid4(),
        ingestion_url="http://ingestion.test",
        speed=1_000_000.0,
        chunk_seconds=1.0,
    )

    assert len(sent) == seconds
    assert b'"ppg"' in sent[0].content
