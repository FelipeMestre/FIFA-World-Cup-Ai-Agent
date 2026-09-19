"""Task-queue (Arq) configuration. Reuses the existing bare `REDIS_URL` env
var already used by `infra/redis/config.py` -- no second prefix, same Redis
instance backs both the conversation cache and the ingestion job queue.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TaskQueueConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str
    JOB_TIMEOUT_SECONDS: int = 1800


task_queue_settings = TaskQueueConfig()
