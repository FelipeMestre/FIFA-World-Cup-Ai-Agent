from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Conversation:
    """A conversation is identified by an id; its message history lives in
    Redis (see `infra/redis/conversation_cache_repository.py`), not Postgres --
    there is no `conversation` table.
    """

    id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
