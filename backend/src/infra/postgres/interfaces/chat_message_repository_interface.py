from typing import Protocol
from uuid import UUID

from src.domain.chat.model.chat_message import ChatMessage, ChatMessageRole


class ChatMessageRepositoryInterface(Protocol):
    async def append_message(
        self,
        conversation_id: UUID,
        role: ChatMessageRole,
        content: str,
        widgets: list[tuple[str, str, dict]] | None = None,
    ) -> ChatMessage: ...
    async def list_for_conversation(
        self, conversation_id: UUID, user_id: int
    ) -> list[ChatMessage]: ...
