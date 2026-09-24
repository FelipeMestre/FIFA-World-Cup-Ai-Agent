from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.infra.postgres.config import engine
from src.infra.redis.config import redis_client
from src.infra.task_queue.pool import close_pool_for_testing
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


@pytest.fixture(autouse=True)
async def _disconnect_redis_client_after_test() -> AsyncGenerator[None]:
    # Same class of bug as `_dispose_postgres_engine_after_test`, for
    # `redis_client` (infra/redis/config.py): it is also a process-wide
    # singleton, created once at import time, whose connection pool binds
    # its first connection to whatever event loop is running when a test
    # first uses it. A later test's fresh event loop reusing that pooled
    # connection breaks -- surfaced as "Event loop is closed" or a hung
    # read, only when more than one test in a run actually touches real
    # Redis (most existing tests override the cache repository with an
    # in-memory fake instead, which is why this went unnoticed until a test
    # exercised the real client across multiple tests in one file). A no-op
    # for tests that never touch Redis (the pool has nothing pooled to
    # close).
    yield
    await redis_client.aclose()


@pytest.fixture(autouse=True)
async def _close_arq_pool_after_test() -> AsyncGenerator[None]:
    # Same class of bug as the two fixtures above, for `pool.py`'s
    # module-level arq connection pool -- see `close_pool_for_testing`'s
    # docstring. A no-op for tests that never enqueue a job.
    yield
    await close_pool_for_testing()
