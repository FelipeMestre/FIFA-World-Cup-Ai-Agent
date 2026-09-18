class ChatError(Exception):
    """Base exception for the chat bounded context."""


class ChatServiceUnavailable(ChatError):
    """Raised when the upstream LLM provider cannot fulfill a chat completion."""
