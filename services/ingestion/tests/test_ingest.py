from fastapi.testclient import TestClient

from ingestion import kafka_producer
from ingestion.main import app


def test_ingest_signal_batch_accepted(monkeypatch):
    sent = []

    async def fake_send(batch):
        sent.append(batch)

    # Avoid a real Kafka connection (TestClient(app) without a context manager
    # doesn't run the app's lifespan, so the module-level producer singleton
    # is never started) — patch its send() instead.
    monkeypatch.setattr(kafka_producer.producer, "send", fake_send)

    client = TestClient(app)
    response = client.post(
        "/api/v1/devices/11111111-1111-1111-1111-111111111111/signals",
        json={
            "signal_type": "ppg",
            "sample_rate_hz": 64.0,
            "start_ts": 0.0,
            "values": [0.1, 0.2, 0.3],
        },
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": 3}
    assert len(sent) == 1
    assert sent[0].signal_type == "ppg"
    assert sent[0].values == [0.1, 0.2, 0.3]
