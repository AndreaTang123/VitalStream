from vitalstream_common.schemas import Role

from tests.conftest import auth_headers, make_user


async def test_patient_cannot_view_another_patients_insights(client, db_session):
    patient_a = await make_user(db_session, role=Role.PATIENT, email="a@example.com")
    patient_b = await make_user(db_session, role=Role.PATIENT, email="b@example.com")

    response = await client.get(
        f"/api/v1/users/{patient_b.id}/insights", headers=auth_headers(patient_a)
    )

    assert response.status_code == 403


async def test_patient_can_view_own_insights(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="own@example.com")

    response = await client.get(
        f"/api/v1/users/{patient.id}/insights", headers=auth_headers(patient)
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_coach_can_view_any_patients_insights(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="coach@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="patient3@example.com")

    response = await client.get(
        f"/api/v1/users/{patient.id}/insights", headers=auth_headers(coach)
    )

    assert response.status_code == 200


async def test_audit_logs_forbidden_for_patient(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="patient4@example.com")

    response = await client.get("/api/v1/audit-logs", headers=auth_headers(patient))

    assert response.status_code == 403


async def test_audit_logs_allowed_for_coach(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="coach2@example.com")

    response = await client.get("/api/v1/audit-logs", headers=auth_headers(coach))

    assert response.status_code == 200
