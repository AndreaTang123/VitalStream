import uuid
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from vitalstream_common.schemas import DeviceStatus, Role

from api.auth import create_access_token, hash_password
from api.db.base import Base, get_db
from api.db.models import CoachPatientORM, DeviceORM, UserORM
from api.main import app

# `features` belongs to feature_extraction's own Base (a different physical
# service, same physical Postgres in real deployments) — api's Alembic
# migrations never create it, so the in-memory sqlite test DB needs it
# declared by hand for routers/features.py's raw-SQL query to have something
# to select from.
_FEATURES_TABLE_DDL = text(
    """
    CREATE TABLE features (
        id TEXT PRIMARY KEY,
        device_id TEXT,
        feature_type TEXT,
        value REAL,
        window TEXT,
        algo_version TEXT,
        window_end TIMESTAMP
    )
    """
)

# insight_service-owned, same reasoning as _FEATURES_TABLE_DDL — see
# routers/users.py's _DEVICE_INSIGHTS_QUERY comment.
_DEVICE_INSIGHTS_TABLE_DDL = text(
    """
    CREATE TABLE device_insights (
        id TEXT PRIMARY KEY,
        device_id TEXT,
        insight_text TEXT,
        feature_snapshot TEXT,
        model TEXT,
        prompt_version TEXT,
        cache_hit BOOLEAN,
        latency_ms REAL,
        generated_at TIMESTAMP,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        cost_usd REAL
    )
    """
)


@pytest_asyncio.fixture
async def db_session():
    # StaticPool keeps every session on the same underlying connection, since
    # sqlite's `:memory:` database is otherwise scoped per-connection — without
    # it, requests made through the app's overridden get_db() would see an
    # empty database even though the fixture just wrote to "the same" engine.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(_FEATURES_TABLE_DDL)
        await conn.execute(_DEVICE_INSIGHTS_TABLE_DDL)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with session_maker() as session:
        yield session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def make_user(db_session, role: Role, email: str) -> UserORM:
    user = UserORM(
        email=email,
        hashed_password=hash_password("password123"),
        role=role,
        created_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    return user


def auth_headers(user: UserORM) -> dict:
    token = create_access_token(user.id, user.role, user.email)
    return {"Authorization": f"Bearer {token}"}


async def make_device(db_session, owner: UserORM, device_type: str = "simulated-ppg") -> DeviceORM:
    device = DeviceORM(
        id=uuid.uuid4(),
        user_id=owner.id,
        device_type=device_type,
        status=DeviceStatus.ACTIVE,
        bound_at=datetime.now(UTC),
    )
    db_session.add(device)
    await db_session.commit()
    return device


async def grant_coach_access(db_session, coach: UserORM, patient: UserORM) -> None:
    db_session.add(
        CoachPatientORM(
            coach_id=coach.id,
            patient_id=patient.id,
            granted_at=datetime.now(UTC),
            granted_by=None,
        )
    )
    await db_session.commit()
