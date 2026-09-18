from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str


redis_settings = RedisConfig()

redis_client: Redis = Redis.from_url(redis_settings.REDIS_URL, decode_responses=True)


async def get_redis() -> Redis:
    return redis_client
