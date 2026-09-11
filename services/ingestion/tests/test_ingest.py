from fastapi.testclient import TestClient

from ingestion import device_registry, kafka_producer
from ingestion.config import settings
from ingestion.main import app

DEVICE_ID = "11111111-1111-1111-1111-111111111111"


def _client(monkeypatch, *, registered: bool = True):
    sent = []

    async def fake_send(batch):
        sent.append(batch)

    monkeypatch.setattr(kafka_producer.producer, "send", fake_send)
    monkeypatch.setattr(
        device_registry.device_registry, "is_registered", lambda device_id: registered
    )
    return TestClient(app), sent


def _post(client, headers=None):
    return client.post(
        f"/api/v1/devices/{DEVICE_ID}/signals",
        json={
            "signal_type": "ppg",
            "sample_rate_hz": 64.0,
            "start_ts": 0.0,
            "values": [0.1, 0.2, 0.3],
        },
        headers=headers or {},
    )


def test_ingest_signal_batch_accepted_with_valid_token(monkeypatch):
    client, sent = _client(monkeypatch, registered=True)

    response = _post(client, headers={"X-Service-Token": settings.service_token})

    assert response.status_code == 202
    assert response.json() == {"accepted": 3}
    assert len(sent) == 1
    assert sent[0].signal_type == "ppg"
    assert sent[0].values == [0.1, 0.2, 0.3]


def test_ingest_rejects_missing_service_token(monkeypatch):
    client, sent = _client(monkeypatch, registered=True)

    response = _post(client)

    assert response.status_code == 401
    assert sent == []


def test_ingest_rejects_wrong_service_token(monkeypatch):
    client, sent = _client(monkeypatch, registered=True)

    response = _post(client, headers={"X-Service-Token": "wrong-token"})

    assert response.status_code == 401
    assert sent == []


def test_ingest_rejects_unregistered_device(monkeypatch):
    client, sent = _client(monkeypatch, registered=False)

    response = _post(client, headers={"X-Service-Token": settings.service_token})

    assert response.status_code == 404
    assert sent == []
