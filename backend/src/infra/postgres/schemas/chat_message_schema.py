"""Durable, append-only chat message log -- source of truth for conversation
history. Never UPDATEd by application code, only INSERTed; `sequence` gives
monotonic per-conversation ordering, assigned by the repository layer.
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infra.postgres.schemas.base import Base

if TYPE_CHECKING:
    from src.infra.postgres.schemas.chat_message_widget_schema import ChatMessageWidgetSchema


class ChatMessageRole(StrEnum):
    """Turn-visible roles only -- this table never stores system/tool
    messages."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatMessageSchema(Base):
    __tablename__ = "chat_message"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[ChatMessageRole] = mapped_column(
        SAEnum(ChatMessageRole, name="chat_message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    widgets: Mapped[list["ChatMessageWidgetSchema"]] = relationship(
        "ChatMessageWidgetSchema", order_by="ChatMessageWidgetSchema.id", lazy="raise"
    )
