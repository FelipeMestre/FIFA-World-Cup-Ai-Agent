from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(slots=True)
class ChatTurnFailure:
    """Marks that generation failed for a given user message -- kept in its
    own table, never in `chat_message`, so a failed turn is never sent back
    to the LLM when reconstructing conversation history (it would silently
    poison the prompt-cache-stable history with content the model never
    produced). Only meaningful when `user_message_id` is still the last
    message in its conversation; a later message means the user retried and
    the failure is stale (see `conversation_router.py`'s
    `get_conversation_messages`, the only reader of this table).
    """

    id: int
    conversation_id: UUID
    user_message_id: int
    detail: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
