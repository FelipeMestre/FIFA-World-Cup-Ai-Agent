"""Widgets attached to an assistant message. Kept in a separate table (FK
to `chat_message.id`) instead of merged into `chat_message.content`, to
protect LLM prompt-cache stability. Append-only and additive-only.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class ChatMessageWidgetSchema(Base):
    __tablename__ = "chat_message_widget"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_message.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(nullable=False)
    # Deliberately a plain string, not a normalized enum/reference table --
    # an explicit prior decision in this codebase.
    widget_type: Mapped[str] = mapped_column(nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
