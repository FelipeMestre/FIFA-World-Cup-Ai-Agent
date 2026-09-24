from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from src.domain.chat.model.chat_message_widget import ChatMessageWidget

# Mirrors `infra.postgres.schemas.chat_message_schema.ChatMessageRole` --
# kept as a plain domain-owned Literal (not an import of the SQLAlchemy
# schema enum) so the domain layer does not depend on infra concretely; the
# repository's `_to_domain` mapper is the single place that translates
# between the two.
ChatMessageRole = Literal["user", "assistant"]


@dataclass(slots=True)
class ChatMessage:
    """A single turn in the durable, append-only `chat_message` log --
    source of truth for conversation history (see `chat_message_schema.py`).
    Never UPDATEd once inserted.
    """

    id: int
    conversation_id: UUID
    sequence: int
    role: ChatMessageRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    widgets: list[ChatMessageWidget] = field(default_factory=list)
