from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(slots=True)
class Conversation:
    """A durable conversation record, persisted in the `conversation`
    Postgres table (source of truth). Its message history lives in
    `chat_message` (see `infra/postgres/repositories/chat_message_repository.py`);
    Redis (`infra/redis/repositories/conversation_cache_repository.py`) is a
    read-through cache in front of it, not the source of truth.
    """

    id: UUID
    user_id: int
    title: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
