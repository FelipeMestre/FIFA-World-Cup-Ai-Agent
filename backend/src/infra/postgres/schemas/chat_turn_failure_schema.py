"""Marks that generation failed for a given `chat_message`. Kept out of
`chat_message`/`chat_message_widget` entirely -- see the domain model's
docstring for why a failed turn must never be sent back to the LLM as
conversation history.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class ChatTurnFailureSchema(Base):
    __tablename__ = "chat_turn_failure"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=False, index=True
    )
    # UNIQUE: at most one failure marker per user message -- a retry always
    # creates a brand-new `chat_message` row instead of reusing this one.
    user_message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_message.id"), nullable=False, unique=True
    )
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
