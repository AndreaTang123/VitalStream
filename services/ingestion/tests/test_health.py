from fastapi.testclient import TestClient

from ingestion.main import app


def test_healthz():
    # Note: deliberately not using TestClient as a context manager here, since
    # that would trigger the app's lifespan (and a real Kafka connection attempt).
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["event_loop"]  # non-empty: proves the handler ran on a real loop
