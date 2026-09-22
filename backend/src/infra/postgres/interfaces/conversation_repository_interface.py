from typing import Protocol
from uuid import UUID

from src.domain.chat.model.conversation import Conversation


class ConversationRepositoryInterface(Protocol):
    async def get_or_create(
        self, conversation_id: UUID, user_id: int, default_title: str
    ) -> Conversation: ...
    async def get_owned(self, conversation_id: UUID, user_id: int) -> Conversation | None: ...
    async def list_for_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[Conversation]: ...
    async def update_title(
        self, conversation_id: UUID, user_id: int, title: str
    ) -> Conversation | None: ...
    async def touch(self, conversation_id: UUID) -> None: ...
