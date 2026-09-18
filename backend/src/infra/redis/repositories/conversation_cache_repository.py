import json
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from src.domain.chat.model.message import Message
from src.infra.redis.config import get_redis
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)

_KEY_PREFIX = "chat:conversation:"


class _RedisConversationCacheRepository:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def get_history(self, conversation_id: str) -> list[Message]:
        raw = await self._redis.get(_KEY_PREFIX + conversation_id)
        if raw is None:
            return []
        payload = json.loads(raw)
        return [Message(role=item["role"], content=item["content"]) for item in payload]

    async def save_history(
        self, conversation_id: str, messages: list[Message], ttl_seconds: int
    ) -> None:
        payload = json.dumps([{"role": m.role, "content": m.content} for m in messages])
        await self._redis.set(_KEY_PREFIX + conversation_id, payload, ex=ttl_seconds)


def get_conversation_cache_repository(
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> ConversationCacheRepositoryInterface:
    return _RedisConversationCacheRepository(redis_client)
