from typing import Protocol


class OpenRouterClientInterface(Protocol):
    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> str: ...
