from typing import Protocol
from uuid import UUID


class ChatTurnFailureRepositoryInterface(Protocol):
    async def record_failure(
        self, conversation_id: UUID, user_message_id: int, detail: str
    ) -> None: ...
    async def get_detail_for_message(self, user_message_id: int) -> str | None: ...
