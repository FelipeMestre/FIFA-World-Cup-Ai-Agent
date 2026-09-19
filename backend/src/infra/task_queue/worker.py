"""Arq worker entrypoint: `arq src.infra.task_queue.worker.WorkerSettings`."""

from arq.connections import RedisSettings

from src.infra.task_queue.config import task_queue_settings
from src.infra.task_queue.tasks import synthetic_upload_task, transfermarkt_sync_task


class WorkerSettings:
    functions = (synthetic_upload_task, transfermarkt_sync_task)
    redis_settings = RedisSettings.from_dsn(task_queue_settings.REDIS_URL)
    job_timeout = task_queue_settings.JOB_TIMEOUT_SECONDS
