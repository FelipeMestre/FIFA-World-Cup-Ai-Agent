import httpx

from src.infra.openrouter.config import OpenRouterConfig, openrouter_settings
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface


class _HttpxOpenRouterClient:
    """OpenAI-compatible chat completion client for OpenRouter.

    `tools` is accepted and forwarded as-is (OpenAI/OpenRouter tool-calling
    schema) so a future phase can wire real analytics tools without changing
    this client's signature. No tool implementations exist yet.
    """

    def __init__(self, config: OpenRouterConfig) -> None:
        self._config = config

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> str:
        body: dict = {"model": self._config.MODEL, "messages": messages}
        if tools:
            body["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._config.API_KEY}",
            "HTTP-Referer": self._config.APP_URL,
            "X-Title": self._config.APP_NAME,
        }

        async with httpx.AsyncClient(base_url=self._config.BASE_URL, timeout=60.0) as client:
            response = await client.post("/chat/completions", json=body, headers=headers)

        if response.status_code >= 400:
            raise OpenRouterRequestFailed(response.status_code, response.text)

        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterRequestFailed(
                response.status_code, "Unexpected response shape"
            ) from exc


def get_openrouter_client() -> OpenRouterClientInterface:
    return _HttpxOpenRouterClient(openrouter_settings)
