from datetime import UTC, datetime, timedelta

from vitalstream_common.schemas import Role

from api.db.models import InsightORM
from api.routers.users import text as users_text
from tests.conftest import auth_headers, make_device, make_user


async def _insert_device_insight(db_session, device_id, generated_at, content="autonomous insight"):
    await db_session.execute(
        users_text(
            "INSERT INTO device_insights "
            "(id, device_id, insight_text, model, prompt_version, cache_hit, generated_at, cost_usd) "
            "VALUES (:id, :device_id, :content, 'gpt-4o-mini', 'v1', 0, :generated_at, 0.001)"
        ),
        {
            "id": f"di-{generated_at.isoformat()}",
            # sqlite has no native uuid type — SQLAlchemy's generic Uuid
            # column (devices.id) stores it as 32-char hex, no dashes, on
            # this backend (Postgres would store dashed-native-uuid, where
            # str(device_id) joins fine instead).
            "device_id": device_id.hex,
            "content": content,
            "generated_at": generated_at,
        },
    )
    await db_session.commit()


async def test_insights_merges_on_demand_and_device_pipeline_sources(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="merge1@example.com")
    device = await make_device(db_session, patient)
    now = datetime.now(UTC)

    db_session.add(
        InsightORM(
            user_id=patient.id,
            content="on-demand insight",
            model_version="gpt-4o-mini",
            eval_score=None,
            created_at=now,
        )
    )
    await db_session.commit()
    await _insert_device_insight(db_session, device.id, now - timedelta(minutes=1))

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(patient))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    sources = {row["source"] for row in body}
    assert sources == {"on_demand", "device"}
    # newest first
    assert body[0]["content"] == "on-demand insight"
    assert body[1]["content"] == "autonomous insight"
    assert body[1]["cost_usd"] == 0.001
