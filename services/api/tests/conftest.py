from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from vitalstream_common.schemas import Role

from api.auth import create_access_token, hash_password
from api.db.base import Base, get_db
from api.db.models import UserORM
from api.main import app


@pytest_asyncio.fixture
async def db_session():
    # StaticPool keeps every session on the same underlying connection, since
    # sqlite's `:memory:` database is otherwise scoped per-connection — without
    # it, requests made through the app's overridden get_db() would see an
    # empty database even though the fixture just wrote to "the same" engine.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
