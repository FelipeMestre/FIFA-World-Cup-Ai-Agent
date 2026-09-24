from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions.chat_exceptions import ConversationOwnershipError
from src.domain.chat.model.conversation import Conversation
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)
from src.infra.postgres.schemas.conversation_schema import ConversationSchema


def _to_domain(row: ConversationSchema) -> Conversation:
    return Conversation(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        icon=row.icon,
        title_is_generated=row.title_is_generated,
    )


class _SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self, conversation_id: UUID, user_id: int, default_title: str
    ) -> tuple[Conversation, bool]:
        """Deliberately does NOT `commit()` -- only `add()`/`flush()`. This
        write participates in the caller's larger atomic transaction (the
        first `chat_message` insert for a brand-new conversation must land
        in the same transaction as this row's creation); the caller commits
        once. This is a documented deviation from this repository layer's
        usual per-call-commit convention.

        Returns `(conversation, created)` -- `created` is True only when
        this call inserted the row, so the caller can enqueue the
        categorization job exactly once per conversation.
        """
        row = await self._session.get(ConversationSchema, conversation_id)
        if row is not None:
            if row.user_id != user_id:
                raise ConversationOwnershipError(
                    f"conversation {conversation_id} is not owned by user {user_id}"
                )
            return _to_domain(row), False

        row = ConversationSchema(id=conversation_id, user_id=user_id, title=default_title)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row), True

    async def is_available_to(self, conversation_id: UUID, user_id: int) -> bool:
        """True when the conversation does not exist yet or belongs to `user_id`.

        A client-minted id is connected before the first message creates the
        row. An existing row owned by someone else is not available.
        """
        row = await self._session.get(ConversationSchema, conversation_id)
        return row is None or row.user_id == user_id

    async def get_owned(self, conversation_id: UUID, user_id: int) -> Conversation | None:
        row = await self._session.get(ConversationSchema, conversation_id)
        if row is None or row.user_id != user_id:
            # Never distinguish "missing" from "exists but not yours" -- both
            # collapse to `None` so existence is never leaked to a non-owner.
            return None
        return _to_domain(row)

    async def list_for_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        result = await self._session.execute(
            select(ConversationSchema)
            .where(ConversationSchema.user_id == user_id)
            .order_by(ConversationSchema.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def update_title(
        self, conversation_id: UUID, user_id: int, title: str
    ) -> Conversation | None:
        """Does not `commit()` -- `flush()` only; same rationale as
        `get_or_create` (the caller owns the transaction boundary).

        A manual rename permanently hands title ownership to the user:
        `title_is_generated` flips to False so a later `update_category`
        call from the categorization job never overwrites it.
        """
        row = await self._session.get(ConversationSchema, conversation_id)
        if row is None or row.user_id != user_id:
            return None
        row.title = title
        row.title_is_generated = False
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row)

    async def update_category(
        self, conversation_id: UUID, title: str, icon: str
    ) -> Conversation | None:
        """Persists the categorization job's result. No ownership check --
        unlike `update_title`, this is called from a background job with a
        trusted `conversation_id` it just resolved for itself, not from a
        user-facing request with a caller-supplied `user_id` to verify
        against.

        `icon` is always written; `title` is written only when the current
        title is still LLM-generated (`title_is_generated`), so a manual
        rename that happened while the job was running is never clobbered.

        Does not `commit()` -- `flush()` only; same rationale as
        `get_or_create`.
        """
        row = await self._session.get(ConversationSchema, conversation_id)
        if row is None:
            return None
        if row.title_is_generated:
            row.title = title
        row.icon = icon
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row)

    async def touch(self, conversation_id: UUID) -> None:
        """Does not `commit()` -- `flush()` only; same rationale as
        `get_or_create`."""
        await self._session.execute(
            update(ConversationSchema)
            .where(ConversationSchema.id == conversation_id)
            .values(updated_at=func.now())
        )
        await self._session.flush()


def get_conversation_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationRepositoryInterface:
    return _SqlAlchemyConversationRepository(session)
