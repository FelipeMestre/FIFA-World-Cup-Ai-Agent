"""Each pytest-asyncio test function gets its own event loop, but
`infra.task_queue.pool`'s Redis connection is cached as a module-level
singleton across the whole process -- reset it between tests so a later
test's loop doesn't try to reuse a connection bound to an already-closed
loop from an earlier test.
"""

import pytest

from src.infra.task_queue import pool as task_queue_pool


@pytest.fixture(autouse=True)
async def _reset_arq_pool():
    yield
    if task_queue_pool._pool is not None:
        await task_queue_pool._pool.aclose()
        task_queue_pool._pool = None
