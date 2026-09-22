from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class ConversationSchema(Base):
    __tablename__ = "conversation"

    # Client-generated (crypto.randomUUID()) -- no server-side default. The
    # id is always supplied by the caller so it can be pushed into the URL
    # before the first message is sent.
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Bumped whenever a new message is appended so the sidebar can order by
    # last activity -- unlike `chat_message`, this row is mutable.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
