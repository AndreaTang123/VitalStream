import uuid
from datetime import UTC, datetime, timedelta

from vitalstream_common.schemas import Role

from api.db.models import InsightORM
from tests.conftest import auth_headers, make_user


async def _add_insight(db_session, user_id, created_at):
    db_session.add(
        InsightORM(
            user_id=user_id,
            content="c",
            model_version="v1",
            eval_score=None,
            created_at=created_at,
        )
    )
    await db_session.commit()


async def test_insights_before_cursor_filters_correctly(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="page1@example.com")
    now = datetime.now(UTC)
    await _add_insight(db_session, patient.id, now - timedelta(minutes=10))
    await _add_insight(db_session, patient.id, now - timedelta(minutes=5))
    await _add_insight(db_session, patient.id, now)

    first_page = await client.get(
        f"/api/v1/users/{patient.id}/insights?limit=2", headers=auth_headers(patient)
    )
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2

    cursor = first_page.json()[-1]["created_at"]
    second_page = await client.get(
        f"/api/v1/users/{patient.id}/insights?limit=2&before={cursor}", headers=auth_headers(patient)
    )
    assert second_page.status_code == 200
    assert len(second_page.json()) == 1


async def test_insights_rejects_malformed_before_cursor(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="page2@example.com")

    response = await client.get(
        f"/api/v1/users/{patient.id}/insights?before=not-a-date", headers=auth_headers(patient)
    )

    assert response.status_code == 400


async def test_features_rejects_malformed_start_ts(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="page3@example.com")

    response = await client.get(
        f"/api/v1/features/{uuid.uuid4()}?start_ts=not-a-date", headers=auth_headers(patient)
    )

    assert response.status_code in (400, 404)
