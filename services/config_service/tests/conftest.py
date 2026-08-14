import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import config_service.main as main_module
from config_service.store import ConfigStore


@pytest_asyncio.fixture(autouse=True)
async def config_store():
    # In-memory sqlite instead of the real Postgres DSN config_store is built
    # with at import time — StaticPool keeps every session on the same
    # connection, since sqlite ":memory:" is otherwise scoped per-connection.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    store = ConfigStore(engine)
    await store.start()

    main_module.config_store = store
    yield store

    await store.stop()
