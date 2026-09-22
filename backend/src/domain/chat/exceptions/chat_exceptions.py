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
