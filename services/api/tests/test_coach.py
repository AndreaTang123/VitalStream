from vitalstream_common.schemas import Role

from tests.conftest import auth_headers, make_user


async def test_admin_can_grant_coach_access(client, db_session):
    admin = await make_user(db_session, role=Role.ADMIN, email="grant-admin@example.com")
    coach = await make_user(db_session, role=Role.COACH, email="grant-coach@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="grant-patient@example.com")

    response = await client.post(
        "/api/v1/coach/patients",
        json={"coach_id": str(coach.id), "patient_id": str(patient.id)},
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    # the grant actually takes effect for resource-level RBAC
    follow_up = await client.get(
        f"/api/v1/users/{patient.id}/insights", headers=auth_headers(coach)
    )
    assert follow_up.status_code == 200


async def test_non_admin_cannot_grant_coach_access(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="grant-coach2@example.com")
    patient = await make_user(db_session, role=Role.PATIENT, email="grant-patient2@example.com")

    response = await client.post(
        "/api/v1/coach/patients",
        json={"coach_id": str(coach.id), "patient_id": str(patient.id)},
        headers=auth_headers(coach),
    )

    assert response.status_code == 403


async def test_grant_rejects_role_mismatch(client, db_session):
    admin = await make_user(db_session, role=Role.ADMIN, email="grant-admin2@example.com")
    patient_a = await make_user(db_session, role=Role.PATIENT, email="grant-patient-a@example.com")
    patient_b = await make_user(db_session, role=Role.PATIENT, email="grant-patient-b@example.com")

    response = await client.post(
        "/api/v1/coach/patients",
        json={"coach_id": str(patient_a.id), "patient_id": str(patient_b.id)},
        headers=auth_headers(admin),
    )

    assert response.status_code == 400


async def test_list_coach_patients_scoped_to_grants(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="list-coach-x@example.com")
    granted = await make_user(db_session, role=Role.PATIENT, email="list-granted@example.com")
    ungranted = await make_user(db_session, role=Role.PATIENT, email="list-ungranted@example.com")

    grant = await client.post(
        "/api/v1/coach/patients",
        json={"coach_id": str(coach.id), "patient_id": str(granted.id)},
        headers=auth_headers(await make_user(db_session, role=Role.ADMIN, email="list-admin@example.com")),
    )
    assert grant.status_code == 201

    response = await client.get("/api/v1/coach/patients", headers=auth_headers(coach))

    assert response.status_code == 200
    ids = {p["id"] for p in response.json()}
    assert str(granted.id) in ids
    assert str(ungranted.id) not in ids


async def test_list_coach_patients_forbidden_for_patient(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="list-forbidden@example.com")

    response = await client.get("/api/v1/coach/patients", headers=auth_headers(patient))

    assert response.status_code == 403
