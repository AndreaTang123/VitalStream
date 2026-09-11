from vitalstream_common.schemas import Role

from tests.conftest import auth_headers, grant_coach_access, make_device, make_user


async def test_patient_can_bind_a_device(client, db_session):
    patient = await make_user(db_session, role=Role.PATIENT, email="bind1@example.com")

    response = await client.post(
        "/api/v1/devices", json={"device_type": "simulated-ppg"}, headers=auth_headers(patient)
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(patient.id)


async def test_coach_cannot_bind_a_device(client, db_session):
    coach = await make_user(db_session, role=Role.COACH, email="bind2@example.com")

    response = await client.post(
        "/api/v1/devices", json={"device_type": "simulated-ppg"}, headers=auth_headers(coach)
    )

    assert response.status_code == 403


async def test_device_list_is_scoped_per_role(client, db_session):
    owner = await make_user(db_session, role=Role.PATIENT, email="list-owner@example.com")
    stranger = await make_user(db_session, role=Role.PATIENT, email="list-stranger@example.com")
    coach = await make_user(db_session, role=Role.COACH, email="list-coach@example.com")
    admin = await make_user(db_session, role=Role.ADMIN, email="list-admin@example.com")
    await make_device(db_session, owner)
    await grant_coach_access(db_session, coach, owner)

    owner_resp = await client.get("/api/v1/devices", headers=auth_headers(owner))
    stranger_resp = await client.get("/api/v1/devices", headers=auth_headers(stranger))
    coach_resp = await client.get("/api/v1/devices", headers=auth_headers(coach))
    admin_resp = await client.get("/api/v1/devices", headers=auth_headers(admin))

    assert len(owner_resp.json()) == 1
    assert stranger_resp.json() == []
    assert len(coach_resp.json()) == 1
    assert len(admin_resp.json()) == 1
