from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class ChatMessageWidget:
    """A widget attached to an assistant `ChatMessage`, persisted in the
    `chat_message_widget` table. Kept separate from `ChatMessage.content` to
    protect LLM prompt-cache stability (see `chat_message_widget_schema.py`).
    """

    id: int
    message_id: int
    tool_name: str
    widget_type: str
    data: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
