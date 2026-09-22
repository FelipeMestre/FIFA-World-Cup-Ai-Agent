from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.chat.model.chat_message import ChatMessage, ChatMessageRole
from src.domain.chat.model.chat_message_widget import ChatMessageWidget
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.chat_message_repository_interface import (
    ChatMessageRepositoryInterface,
)
from src.infra.postgres.schemas.chat_message_schema import ChatMessageRole as SchemaRole
from src.infra.postgres.schemas.chat_message_schema import ChatMessageSchema
from src.infra.postgres.schemas.chat_message_widget_schema import ChatMessageWidgetSchema
from src.infra.postgres.schemas.conversation_schema import ConversationSchema


def _widget_to_domain(row: ChatMessageWidgetSchema) -> ChatMessageWidget:
    return ChatMessageWidget(
        id=row.id,
        message_id=row.message_id,
        tool_name=row.tool_name,
        widget_type=row.widget_type,
        data=row.data,
        created_at=row.created_at,
    )


def _to_domain(row: ChatMessageSchema) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        conversation_id=row.conversation_id,
        sequence=row.sequence,
        role=row.role.value,
        content=row.content,
        created_at=row.created_at,
        widgets=[_widget_to_domain(widget) for widget in row.widgets],
    )


class _SqlAlchemyChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_message(
        self,
        conversation_id: UUID,
        role: ChatMessageRole,
        content: str,
        widgets: list[tuple[str, str, dict]] | None = None,
    ) -> ChatMessage:
        """Deliberately does NOT `commit()` -- only `add()`/`flush()`. This
        is the append-only, single-turn-atomic write path: the `sequence`
        lookup below, this message insert, its widget inserts, and the
        caller's `ConversationRepositoryInterface.touch()` all need to land
        in one transaction that the caller (T4's chat endpoint) commits
        once. The caller owns the transaction boundary.

        Known limitation (accepted at this demo scale): the `MAX(sequence)`
        read below and this insert are not wrapped in a `SELECT ... FOR
        UPDATE` / serializable transaction, so two concurrent writers
        appending to the *same* conversation could race and violate the
        `(conversation_id, sequence)` unique constraint. Not addressed here
        -- no retry/locking logic is built for it.
        """
        next_sequence_result = await self._session.execute(
            select(func.coalesce(func.max(ChatMessageSchema.sequence), 0) + 1).where(
                ChatMessageSchema.conversation_id == conversation_id
            )
        )
        next_sequence = next_sequence_result.scalar_one()

        row = ChatMessageSchema(
            conversation_id=conversation_id,
            sequence=next_sequence,
            role=SchemaRole(role),
            content=content,
        )
        self._session.add(row)
        await self._session.flush()

        widget_rows = [
            ChatMessageWidgetSchema(
                message_id=row.id, tool_name=tool_name, widget_type=widget_type, data=data
            )
            for tool_name, widget_type, data in (widgets or [])
        ]
        if widget_rows:
            self._session.add_all(widget_rows)
            await self._session.flush()

        # Built from `row` + `widget_rows` directly rather than reading
        # `row.widgets` -- the relationship is `lazy="raise"`, and even
        # *assigning* to it triggers SQLAlchemy to load its prior value for
        # history tracking, which would raise here.
        return ChatMessage(
            id=row.id,
            conversation_id=row.conversation_id,
            sequence=row.sequence,
            role=row.role.value,
            content=row.content,
            created_at=row.created_at,
            widgets=[_widget_to_domain(widget) for widget in widget_rows],
        )

    async def list_for_conversation(self, conversation_id: UUID, user_id: int) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessageSchema)
            .join(ConversationSchema, ConversationSchema.id == ChatMessageSchema.conversation_id)
            .where(
                ChatMessageSchema.conversation_id == conversation_id,
                ConversationSchema.user_id == user_id,
            )
            .order_by(ChatMessageSchema.sequence.asc())
            .options(selectinload(ChatMessageSchema.widgets))
        )
        return [_to_domain(row) for row in result.scalars().all()]


def get_chat_message_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatMessageRepositoryInterface:
    return _SqlAlchemyChatMessageRepository(session)
