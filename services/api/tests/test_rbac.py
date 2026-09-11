import uuid

from vitalstream_common.schemas import Role

from tests.conftest import auth_headers, grant_coach_access, make_device, make_user

# --- Core acceptance matrix (week6 Step 4/9): 3 roles x own/authorized/unauthorized. ---


async def test_patient_can_view_own_insights(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="own@example.com")

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(patient))

    assert response.status_code == 200
    assert response.json() == []


async def test_patient_cannot_view_another_patients_insights(client, db_session):
    patient_a = await make_user(db_session, role=Role.PATIENT, email="a@example.com")
    patient_b = await make_user(db_session, role=Role.PATIENT, email="b@example.com")

    response = await client.get(
        f"/api/v1/users/{patient_b.id}/insights", headers=auth_headers(patient_a)
    )

    assert response.status_code == 403


async def test_coach_can_view_authorized_patients_insights(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="coach-auth@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="patient-auth@example.com")
    await grant_coach_access(db_session, coach, patient)

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(coach))

    assert response.status_code == 200


async def test_coach_cannot_view_unauthorized_patients_insights(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="coach-unauth@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="patient-unauth@example.com")

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(coach))

    assert response.status_code == 403


async def test_admin_can_view_any_patients_insights(client, db_session):
    admin = await make_user(db_session, role=Role.ADMIN, email="admin1@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="patient-for-admin@example.com")

    response = await client.get(f"/api/v1/users/{patient.id}/insights", headers=auth_headers(admin))

    assert response.status_code == 200


async def test_device_features_follow_same_resource_rbac(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="coach-dev@example.com")
    owner = await make_user(db_session, role=Role.PATIENT, email="owner-dev@example.com")
    stranger = await make_user(db_session, role=Role.PATIENT, email="stranger-dev@example.com")
    device = await make_device(db_session, owner)
    await grant_coach_access(db_session, coach, owner)

    granted = await client.get(f"/api/v1/features/{device.id}", headers=auth_headers(coach))
    denied = await client.get(f"/api/v1/features/{device.id}", headers=auth_headers(stranger))

    assert granted.status_code == 200
    assert denied.status_code == 403


async def test_unknown_device_returns_404(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="patient-404@example.com")

    response = await client.get(f"/api/v1/features/{uuid.uuid4()}", headers=auth_headers(patient))

    assert response.status_code == 404


# --- Audit-log endpoint's own RBAC (Step 6: the endpoint that guards itself). ---


async def test_audit_logs_forbidden_for_patient(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="patient4@example.com")

    response = await client.get("/api/v1/audit-logs", headers=auth_headers(patient))

    assert response.status_code == 403


async def test_audit_logs_allowed_for_coach(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="coach2@example.com")

    response = await client.get("/api/v1/audit-logs", headers=auth_headers(coach))

    assert response.status_code == 200


async def test_audit_logs_allowed_for_admin(client, db_session):
    admin = await make_user(db_session, role=Role.ADMIN, email="admin2@example.com")

    response = await client.get("/api/v1/audit-logs", headers=auth_headers(admin))

    assert response.status_code == 200
