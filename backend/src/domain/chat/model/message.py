from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

MessageRole = Literal["user", "assistant"]


@dataclass(slots=True)
class Message:
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
