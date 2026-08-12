from vitalstream_common.schemas import Role

from tests.conftest import make_user


async def test_login_succeeds_with_correct_password(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="patient@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "patient@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_rejects_wrong_password(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="patient2@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "patient2@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
