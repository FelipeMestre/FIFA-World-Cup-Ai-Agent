from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.infra.postgres.config import engine
from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _dispose_postgres_engine_after_test() -> AsyncGenerator[None]:
    # pytest-asyncio gives each test function its own event loop, but the
    # postgres engine's connection pool is a process-wide singleton. Without
    # disposing it after every test, a later test's loop can try to reuse a
    # pooled asyncpg connection opened under an already-closed earlier loop,
    # raising "Event loop is closed" intermittently. A no-op for tests that
    # never touch the DB (the pool has nothing pooled to close).
    yield
    await engine.dispose()
