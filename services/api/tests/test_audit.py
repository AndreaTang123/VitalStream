from sqlalchemy import select
from vitalstream_common.schemas import Role

from api.db.models import AuditLogORM
from tests.conftest import auth_headers, grant_coach_access, make_user


async def _audit_rows(db_session):
    result = await db_session.execute(select(AuditLogORM))
    return result.scalars().all()


async def test_cross_user_read_writes_audit_row(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="audit-coach@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="audit-patient@example.com")
    await grant_coach_access(db_session, coach, patient)

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(coach))
    assert response.status_code == 200

    rows = await _audit_rows(db_session)
    matching = [r for r in rows if r.action == "insights.read"]
    assert len(matching) == 1
    assert matching[0].actor_id == coach.id
    assert matching[0].target_user_id == patient.id
    assert matching[0].status == "success"


async def test_self_read_does_not_write_audit_row(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="audit-self@example.com")

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(patient))
    assert response.status_code == 200

    rows = await _audit_rows(db_session)
    assert [r for r in rows if r.action == "insights.read"] == []


async def test_denied_cross_user_access_writes_denied_audit_row(client, db_session):
    patient_a = await make_user(db_session, role=Role.PATIENT, email="audit-a@example.com")
    patient_b = await make_user(db_session, role=Role.PATIENT, email="audit-b@example.com")

    response = await client.get(
        f"/api/v1/users/{patient_b.id}/insights", headers=auth_headers(patient_a)
    )
    assert response.status_code == 403

    rows = await _audit_rows(db_session)
    denied = [r for r in rows if r.status == "denied"]
    assert len(denied) == 1
    assert denied[0].actor_id == patient_a.id
    assert denied[0].target_user_id == patient_b.id


async def test_failed_login_writes_audit_row_with_no_actor_id(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="audit-login@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "audit-login@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401

    rows = await _audit_rows(db_session)
    login_failed = [r for r in rows if r.action == "auth.login_failed"]
    assert len(login_failed) == 1
    assert login_failed[0].actor_id is None
    assert login_failed[0].actor_email == "audit-login@example.com"


async def test_successful_login_writes_audit_row(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="audit-login-ok@example.com")

    response = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": "password123"}
    )
    assert response.status_code == 200

    rows = await _audit_rows(db_session)
    success = [r for r in rows if r.action == "auth.login_success"]
    assert len(success) == 1
    assert success[0].actor_id == user.id
