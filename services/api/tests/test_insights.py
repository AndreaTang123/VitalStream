import httpx
from vitalstream_common.schemas import Role

from api.routers import insights as insights_router
from tests.conftest import auth_headers, make_device, make_user


async def _insert_feature(db_session, device_id, feature_type, value, window_end):
    await db_session.execute(
        insights_router.text(
            "INSERT INTO features (id, device_id, feature_type, value, window, algo_version, window_end) "
            "VALUES (:id, :device_id, :feature_type, :value, 'w', 'v1', :window_end)"
        ),
        {
            "id": f"{device_id}-{feature_type}-{window_end}",
            "device_id": str(device_id),
            "feature_type": feature_type,
            "value": value,
            "window_end": window_end,
        },
    )
    await db_session.commit()


async def test_generate_insight_requires_recent_features(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="gen-nofeat@example.com")
    device = await make_device(db_session, patient)

    response = await client.post(
        "/api/v1/insights/generate",
        json={"user_id": str(patient.id), "device_id": str(device.id)},
        headers=auth_headers(patient),
    )

    assert response.status_code == 409


async def test_generate_insight_uses_latest_feature_per_type(client, db_session, monkeypatch):
    patient = await make_user(db_session, role=Role.PATIENT, email="gen-ok@example.com")
    device = await make_device(db_session, patient)
    await _insert_feature(db_session, device.id, "heart_rate", 70.0, "2026-01-01T00:00:00")
    await _insert_feature(db_session, device.id, "heart_rate", 75.0, "2026-01-01T00:02:00")  # latest

    # Patching httpx.AsyncClient.post at the class level would also intercept
    # the *outer* test client's call into the ASGI app itself (both are
    # AsyncClient instances) — so only fake the call whose base_url is
    # insight_service's, and pass everything else through to the real method.
    seen_payloads = []
    real_post = httpx.AsyncClient.post

    async def fake_post(self, url, json=None, **kwargs):
        if str(self.base_url) != insights_router.settings.insight_service_base_url:
            return await real_post(self, url, json=json, **kwargs)
        seen_payloads.append(json)
        return httpx.Response(
            200,
            json={"content": "looks stable", "model_version": "gpt-4o-mini", "prompt_version": "v1", "cached": False},
            request=httpx.Request("POST", "http://insight.test" + url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = await client.post(
        "/api/v1/insights/generate",
        json={"user_id": str(patient.id), "device_id": str(device.id)},
        headers=auth_headers(patient),
    )

    assert response.status_code == 200
    assert response.json()["content"] == "looks stable"
    assert seen_payloads[0]["features"] == {"heart_rate": 75.0}


async def test_generate_insight_rejects_device_owned_by_someone_else(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="gen-wrongowner@example.com")
    other = await make_user(db_session, role=Role.PATIENT, email="gen-otherowner@example.com")
    device = await make_device(db_session, other)

    response = await client.post(
        "/api/v1/insights/generate",
        json={"user_id": str(patient.id), "device_id": str(device.id)},
        headers=auth_headers(patient),
    )

    assert response.status_code == 404
