"""Arq worker entrypoint: `arq src.infra.task_queue.worker.WorkerSettings`."""

from arq.connections import RedisSettings
from arq.worker import func

from src.infra.task_queue.chat_tasks import categorize_conversation_task, generate_chat_reply_task
from src.infra.task_queue.config import task_queue_settings
from src.infra.task_queue.tasks import (
    bulk_synthetic_upload_task,
    identity_link_rematch_task,
    synthetic_upload_task,
    transfermarkt_sync_task,
)

# 5 minutes, not the shared ingestion default below -- a chat reply is
# request-latency-shaped work, not a batch job; `job_timeout` on
# WorkerSettings applies to every function unless overridden per-function
# via `func(..., timeout=...)`, which is what this does.
CHAT_REPLY_JOB_TIMEOUT_SECONDS = 300

# A single, non-streamed-to-the-user classification call needs far less
# headroom than a full chat reply's 300s above.
CATEGORIZE_JOB_TIMEOUT_SECONDS = 60

# The shared ingestion default below (30 min) isn't enough for this task's
# largest step: `game_lineups.csv.gz` alone is ~126MB, ingested as thousands
# of sequential 500-row upsert commits with no per-file budget of its own.
TRANSFERMARKT_SYNC_JOB_TIMEOUT_SECONDS = 3600


class WorkerSettings:
    functions = (
        synthetic_upload_task,
        bulk_synthetic_upload_task,
        func(transfermarkt_sync_task, timeout=TRANSFERMARKT_SYNC_JOB_TIMEOUT_SECONDS),
        identity_link_rematch_task,
        func(generate_chat_reply_task, timeout=CHAT_REPLY_JOB_TIMEOUT_SECONDS),
        func(categorize_conversation_task, timeout=CATEGORIZE_JOB_TIMEOUT_SECONDS),
    )
    redis_settings = RedisSettings.from_dsn(task_queue_settings.REDIS_URL)
    job_timeout = task_queue_settings.JOB_TIMEOUT_SECONDS
