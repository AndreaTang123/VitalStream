import jwt
from vitalstream_common.schemas import Role

from api.settings import settings
from tests.conftest import auth_headers, make_user


async def test_login_succeeds_with_correct_password(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="patient@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "patient@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_rejects_wrong_password(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="patient2@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "patient2@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_login_error_identical_for_unknown_user_and_wrong_password(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="patient2b@example.com")

    wrong_password = await client.post(
        "/api/v1/auth/login",
        data={"username": "patient2b@example.com", "password": "wrong-password"},
    )
    unknown_user = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "whatever"},
    )

    assert wrong_password.json()["detail"] == unknown_user.json()["detail"]


async def test_register_then_login_full_flow(client, db_session):
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "new-patient@example.com", "password": "s3cret-pass", "display_name": "New Patient"},
    )
    assert register.status_code == 201
    assert register.json()["role"] == "patient"

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "new-patient@example.com", "password": "s3cret-pass"},
    )
    assert login.status_code == 200
    tokens = login.json()

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "new-patient@example.com"


async def test_register_rejects_duplicate_email(client, db_session):
    await make_user(db_session, role=Role.PATIENT, email="dup@example.com")

    response = await client.post(
        "/api/v1/auth/register", json={"email": "dup@example.com", "password": "whatever123"}
    )

    assert response.status_code == 409


async def test_refresh_issues_new_access_token(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="refresh1@example.com")
    login = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_logout_revokes_refresh_token(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="logout1@example.com")
    login = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": "password123"}
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


async def test_access_token_rejected_after_expiry(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="expired@example.com")
    expired_payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "email": user.email,
        "iat": 0,
        "exp": 1,  # 1970-01-01T00:00:01Z, long expired
        "jti": "expired-jti",
        "type": "access",
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


async def test_access_token_rejected_with_wrong_signature(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="forged@example.com")
    forged_token = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "type": "access"},
        "not-the-real-secret",
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"}
    )

    assert response.status_code == 401


async def test_access_token_rejected_with_alg_none(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="algnone@example.com")
    unsigned_token = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "type": "access"}, "", algorithm="none"
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {unsigned_token}"}
    )

    assert response.status_code == 401


async def test_response_never_leaks_password_hash(client, db_session):
    user = await make_user(db_session, role=Role.PATIENT, email="nohash@example.com")

    response = await client.get("/api/v1/auth/me", headers=auth_headers(user))

    assert "password" not in response.json()
    assert "hashed_password" not in response.json()
