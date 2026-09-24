class ChatError(Exception):
    """Base exception for the chat bounded context."""


class ChatServiceUnavailable(ChatError):
    """Raised when the upstream LLM provider cannot fulfill a chat completion."""


class PlayerNotFoundError(ChatError):
    """Raised when a chat-tool query does not resolve to a known player.
    Carries the offending query in its message so the handler can surface
    exactly which side of a lookup failed.
    """


class SamePlayerComparisonError(ChatError):
    """Raised when both sides of a `get_player_comparison` call resolve to
    the same player -- comparing a player against themselves is not a
    meaningful comparison.
    """


class ConversationOwnershipError(ChatError):
    """Raised when a `conversation` row exists for the given id but belongs
    to a different `user_id`. UUID unguessability is never treated as
    authorization -- every read/write on a conversation must check
    ownership server-side (see `odd/tasks/chat-memory.md`). Only raised by
    write paths (e.g. `get_or_create`) that must distinguish "id collision
    owned by someone else" from "id free to claim"; read paths (`get_owned`)
    return `None` instead, so existence of another user's conversation is
    never leaked via an exception vs. `None` distinction.
    """


TURN_ALREADY_IN_PROGRESS_DETAIL = "A reply is already being generated for this conversation"


class TurnAlreadyInProgress(ChatError):
    """Raised when a turn reservation (`SET NX EX` on `turn_in_progress_key`)
    fails because another turn is already in progress for the conversation.
    Turned into an HTTP 409 by `POST /conversations/{id}/messages`
    (`conversation_router.py`), the only send path since the live WebSocket
    route was removed.
    """

    def __init__(self, message: str = TURN_ALREADY_IN_PROGRESS_DETAIL) -> None:
        super().__init__(message)
