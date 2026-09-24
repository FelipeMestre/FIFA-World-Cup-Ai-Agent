from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.chat_turn_failure_repository_interface import (
    ChatTurnFailureRepositoryInterface,
)
from src.infra.postgres.schemas.chat_turn_failure_schema import ChatTurnFailureSchema


class _SqlAlchemyChatTurnFailureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_failure(
        self, conversation_id: UUID, user_message_id: int, detail: str
    ) -> None:
        """Self-commits -- unlike `chat_message`/`conversation`'s
        repositories, this write never participates in a larger atomic
        transaction (see `generate_chat_reply_task`, its only caller: it
        opens a fresh session just for this write)."""
        self._session.add(
            ChatTurnFailureSchema(
                conversation_id=conversation_id, user_message_id=user_message_id, detail=detail
            )
        )
        await self._session.commit()

    async def get_detail_for_message(self, user_message_id: int) -> str | None:
        result = await self._session.execute(
            select(ChatTurnFailureSchema.detail).where(
                ChatTurnFailureSchema.user_message_id == user_message_id
            )
        )
        return result.scalar_one_or_none()


def get_chat_turn_failure_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatTurnFailureRepositoryInterface:
    return _SqlAlchemyChatTurnFailureRepository(session)
