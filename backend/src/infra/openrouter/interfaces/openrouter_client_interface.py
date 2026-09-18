from collections.abc import AsyncIterator
from typing import Protocol

from src.infra.openrouter.schemas import ChatCompletionChunk


class OpenRouterClientInterface(Protocol):
    def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]: ...
