from fastapi.testclient import TestClient

from config_service.main import app

client = TestClient(app)


def test_validate_gray_release_promote_flow():
    register = client.post(
        "/api/v1/config/feature-algo/register-stable",
        json={"algo_name": "resting_heart_rate", "version": "v1"},
    )
    assert register.status_code == 201

    canary = client.post(
        "/api/v1/config/feature-algo",
        json={"algo_name": "resting_heart_rate", "version": "v2", "rollout_pct": 10},
    )
    assert canary.status_code == 201

    active = client.get("/api/v1/config/feature-algo/resting_heart_rate/active").json()
    assert active == {"stable": "v1", "canary": "v2", "rollout_pct": 10}

    promoted = client.post("/api/v1/config/feature-algo/resting_heart_rate/promote")
    assert promoted.status_code == 200

    active_after_promote = client.get("/api/v1/config/feature-algo/resting_heart_rate/active").json()
    assert active_after_promote == {"stable": "v2", "canary": None, "rollout_pct": 0}


def test_rollback_reverts_to_previous_stable():
    client.post(
        "/api/v1/config/feature-algo/register-stable",
        json={"algo_name": "hrv_trend", "version": "v1"},
    )
    client.post(
        "/api/v1/config/feature-algo",
        json={"algo_name": "hrv_trend", "version": "v2-buggy", "rollout_pct": 5},
    )

    rollback = client.post("/api/v1/config/feature-algo/hrv_trend/v2-buggy/rollback")
    assert rollback.status_code == 200

    active = client.get("/api/v1/config/feature-algo/hrv_trend/active").json()
    assert active == {"stable": "v1", "canary": None, "rollout_pct": 0}


def test_publish_canary_rejects_invalid_rollout_pct():
    client.post(
        "/api/v1/config/feature-algo/register-stable",
        json={"algo_name": "sleep_quality", "version": "v1"},
    )

    response = client.post(
        "/api/v1/config/feature-algo",
        json={"algo_name": "sleep_quality", "version": "v2", "rollout_pct": 150},
    )
    assert response.status_code == 422
