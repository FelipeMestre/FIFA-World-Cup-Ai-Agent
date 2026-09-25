"""Redis connection pool + thin enqueue wrappers. Keeps Arq's `enqueue_job`
string-based API out of the admin router -- callers invoke a named function
with typed arguments instead.
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src.infra.task_queue.config import task_queue_settings

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(task_queue_settings.REDIS_URL))
    return _pool


async def close_pool_for_testing() -> None:
    """Test-only: closes and clears the module-level pool. Same class of
    fix as `conftest.py`'s postgres-engine/redis-client fixtures -- this
    pool is a process-wide singleton whose connection binds to whatever
    event loop is running when it is first created, but pytest-asyncio
    gives each test function its own loop. Without this, a later test
    reusing the pool against an already-closed earlier loop raises
    "Event loop is closed". Nothing in the running app calls this.
    """
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue_synthetic_upload(table_name: str, job_id: int, csv_bytes: bytes) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("synthetic_upload_task", job_id, table_name, csv_bytes)


async def enqueue_bulk_synthetic_upload(job_id: int, files: list[tuple[str, bytes]]) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("bulk_synthetic_upload_task", job_id, files)


async def enqueue_transfermarkt_sync(job_id: int, skip_populated: bool = False) -> None:
    # NOTE: the design's optional `table_filter` (partial-table sync) is
    # deferred -- this batch runs the full scoped pipeline only (optionally
    # resuming via skip_populated). Adding a filtered subset later is
    # additive (a new optional param + a check in
    # `TransfermarktSyncService._run_pipeline`), not a breaking change.
    pool = await get_arq_pool()
    await pool.enqueue_job("transfermarkt_sync_task", job_id, skip_populated)


async def enqueue_identity_link_rematch(job_id: int) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("identity_link_rematch_task", job_id)


async def enqueue_chat_reply(
    conversation_id: str, user_id: int, user_message: str, user_message_id: int
) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "generate_chat_reply_task", conversation_id, user_id, user_message, user_message_id
    )


async def enqueue_categorize_conversation(
    conversation_id: str, user_id: int, first_message: str
) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("categorize_conversation_task", conversation_id, user_id, first_message)
