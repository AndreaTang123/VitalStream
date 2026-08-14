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


def test_rollback_after_promote_restores_previous_active():
    """Covers week3-layer1-deepening-guide.md Step 4: rollback must work even
    after a bad version has already been promoted to 100% active, not just
    while it's still a partial-rollout canary."""
    algo = "heart_rate"
    client.post(
        "/api/v1/config/feature-algo/register-stable",
        json={"algo_name": algo, "version": "v1-good", "actor": "alice"},
    )
    client.post(
        "/api/v1/config/feature-algo",
        json={"algo_name": algo, "version": "v2-bad", "rollout_pct": 100, "actor": "alice"},
    )
    client.post(f"/api/v1/config/feature-algo/{algo}/promote", json={"actor": "alice"})

    active = client.get(f"/api/v1/config/feature-algo/{algo}/active").json()
    assert active["stable"] == "v2-bad"

    rollback = client.post(
        f"/api/v1/config/feature-algo/{algo}/v2-bad/rollback", json={"actor": "bob"}
    )
    assert rollback.status_code == 200
    assert rollback.json() == {"rolled_back": "v2-bad", "restored_active": "v1-good"}

    active_after = client.get(f"/api/v1/config/feature-algo/{algo}/active").json()
    assert active_after == {"stable": "v1-good", "canary": None, "rollout_pct": 0}


def test_audit_log_records_every_mutation_with_actor():
    algo = "sleep_score"
    client.post(
        "/api/v1/config/feature-algo/register-stable",
        json={"algo_name": algo, "version": "v1", "actor": "alice"},
    )
    client.post(
        "/api/v1/config/feature-algo",
        json={"algo_name": algo, "version": "v2", "rollout_pct": 20, "actor": "alice"},
    )
    client.post(f"/api/v1/config/feature-algo/{algo}/v2/rollback", json={"actor": "bob"})

    log = client.get(f"/api/v1/config/feature-algo/{algo}/audit-log").json()
    actions = [(entry["action"], entry["actor"]) for entry in log]
    assert ("register_stable", "alice") in actions
    assert ("publish_canary(pct=20)", "alice") in actions
    assert ("rollback", "bob") in actions
