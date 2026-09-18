from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class Message:
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tool_call_id: str | None = None
    """Set only for `role: "tool"` messages -- links the result back to the
    tool call that requested it."""
    name: str | None = None
    """Set only for `role: "tool"` messages -- the tool's name."""
