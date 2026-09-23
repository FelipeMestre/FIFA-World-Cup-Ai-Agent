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


async def enqueue_synthetic_upload(table_name: str, job_id: int, csv_bytes: bytes) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("synthetic_upload_task", job_id, table_name, csv_bytes)


async def enqueue_transfermarkt_sync(job_id: int, skip_populated: bool = False) -> None:
    # NOTE: the design's optional `table_filter` (partial-table sync) is
    # deferred -- this batch runs the full scoped pipeline only (optionally
    # resuming via skip_populated). Adding a filtered subset later is
    # additive (a new optional param + a check in
    # `TransfermarktSyncService._run_pipeline`), not a breaking change.
    pool = await get_arq_pool()
    await pool.enqueue_job("transfermarkt_sync_task", job_id, skip_populated)


async def enqueue_chat_reply(conversation_id: str, user_id: int, user_message: str) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("generate_chat_reply_task", conversation_id, user_id, user_message)
