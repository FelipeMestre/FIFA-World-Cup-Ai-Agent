from typing import Protocol

from src.domain.chat.model.message import Message


class ConversationCacheRepositoryInterface(Protocol):
    async def get_history(self, conversation_id: str) -> list[Message]: ...
    async def save_history(
        self, conversation_id: str, messages: list[Message], ttl_seconds: int
    ) -> None: ...
