"""Arq worker entrypoint: `arq src.infra.task_queue.worker.WorkerSettings`."""

from arq.connections import RedisSettings
from arq.worker import func

from src.infra.task_queue.chat_tasks import generate_chat_reply_task
from src.infra.task_queue.config import task_queue_settings
from src.infra.task_queue.tasks import synthetic_upload_task, transfermarkt_sync_task

# 5 minutes, not the shared ingestion default below -- a chat reply is
# request-latency-shaped work, not a batch job; `job_timeout` on
# WorkerSettings applies to every function unless overridden per-function
# via `func(..., timeout=...)`, which is what this does.
CHAT_REPLY_JOB_TIMEOUT_SECONDS = 300


class WorkerSettings:
    functions = (
        synthetic_upload_task,
        transfermarkt_sync_task,
        func(generate_chat_reply_task, timeout=CHAT_REPLY_JOB_TIMEOUT_SECONDS),
    )
    redis_settings = RedisSettings.from_dsn(task_queue_settings.REDIS_URL)
    job_timeout = task_queue_settings.JOB_TIMEOUT_SECONDS
