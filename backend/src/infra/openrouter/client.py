import json
import logging
from collections.abc import AsyncIterator

import httpx

from src.infra.openrouter.config import OpenRouterConfig, openrouter_settings
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.openrouter.schemas import ChatCompletionChunk, ToolCall

logger = logging.getLogger(__name__)

_DONE_SENTINEL = "[DONE]"


class _HttpxOpenRouterClient:
    """OpenAI-compatible chat completion client for OpenRouter.

    Requests are sent with `"stream": True`. `create_chat_completion` is an
    async generator that yields `ChatCompletionChunk` objects live as
    OpenRouter's own SSE response (`data: {...}` chunks terminated by a
    `data: [DONE]` sentinel) is parsed -- it never waits for the full
    response before yielding anything. Callers that want an aggregated
    final result consume the generator and aggregate it themselves (see
    `chat_service.py`); callers that want to forward live deltas consume
    the generator and pass chunks straight through. `tools` is accepted and
    forwarded as-is (OpenAI/OpenRouter tool-calling schema) so a future
    phase can wire a tool-execution loop without changing this client's
    signature. No tool implementations exist yet.
    """

    def __init__(
        self, config: OpenRouterConfig, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        """`transport` is an injectable seam for tests (e.g. `httpx.MockTransport`
        serving recorded SSE fixtures); production code leaves it `None` and
        httpx uses its real network transport.
        """
        self._config = config
        self._transport = transport

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        body: dict = {
            "models": self._config.MODELS,
            "messages": _apply_system_prompt_caching(messages),
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._config.API_KEY}",
            "HTTP-Referer": self._config.APP_URL,
            "X-Title": self._config.APP_NAME,
        }

        async with (
            httpx.AsyncClient(
                base_url=self._config.BASE_URL, timeout=60.0, transport=self._transport
            ) as client,
            client.stream("POST", "/chat/completions", json=body, headers=headers) as response,
        ):
            if response.status_code >= 400:
                await response.aread()
                raise OpenRouterRequestFailed(response.status_code, response.text)

            tool_call_fragments: dict[int, dict[str, str]] = {}
            async for line in response.aiter_lines():
                chunk = _parse_sse_line(line, tool_call_fragments)
                if chunk is not None:
                    yield chunk


def _apply_system_prompt_caching(messages: list[dict]) -> list[dict]:
    """Convert a leading `role: "system"` message's plain-string `content`
    into a content-block array carrying an ephemeral prompt-cache
    breakpoint, preserving the disclaimer text unchanged. Every other
    message is forwarded as-is.
    """
    if not messages or messages[0].get("role") != "system":
        return messages

    system_message = messages[0]
    content = system_message["content"]
    if isinstance(content, list):
        return messages

    cached_system_message = {
        **system_message,
        "content": [
            {
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }
    return [cached_system_message, *messages[1:]]


def _parse_sse_line(
    line: str, tool_call_fragments: dict[int, dict[str, str]]
) -> ChatCompletionChunk | None:
    """Parse one raw SSE line into a `ChatCompletionChunk`, mutating
    `tool_call_fragments` in place as tool-call argument fragments stream
    in across multiple lines. Returns `None` for lines carrying no
    actionable data (blank lines, the `[DONE]` sentinel, malformed JSON, or
    a payload with no `choices`).

    `tool_calls` is only populated on the chunk carrying `finish_reason`
    (the final chunk of a turn), since tool-call arguments are only fully
    assembled once every fragment has arrived.
    """
    if not line.startswith("data:"):
        return None
    payload = line.removeprefix("data:").strip()
    if not payload or payload == _DONE_SENTINEL:
        return None

    try:
        raw_chunk = json.loads(payload)
    except json.JSONDecodeError:
        return None

    choices = raw_chunk.get("choices") or []
    if not choices:
        return None
    choice = choices[0]
    delta = choice.get("delta") or {}
    finish_reason = choice.get("finish_reason")

    for tool_call_delta in delta.get("tool_calls") or []:
        _accumulate_tool_call_fragment(tool_call_fragments, tool_call_delta)

    usage = raw_chunk.get("usage") or {}
    prompt_tokens_details = usage.get("prompt_tokens_details") or {}
    cached_tokens = prompt_tokens_details.get("cached_tokens")
    cache_write_tokens = usage.get("cache_write_tokens")
    served_model = raw_chunk.get("model")

    tool_calls: list[ToolCall] | None = None
    if finish_reason is not None:
        tool_calls = [
            ToolCall(id=fragment["id"], name=fragment["name"], arguments=fragment["arguments"])
            for _, fragment in sorted(tool_call_fragments.items())
        ]
        logger.info(
            "OpenRouter completion served by model=%s cached_tokens=%s cache_write_tokens=%s",
            served_model,
            cached_tokens,
            cache_write_tokens,
        )

    return ChatCompletionChunk(
        delta_content=delta.get("content") or None,
        delta_reasoning=delta.get("reasoning") or None,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        model=served_model,
        cached_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def _accumulate_tool_call_fragment(
    fragments: dict[int, dict[str, str]], tool_call_delta: dict
) -> None:
    index = tool_call_delta.get("index", 0)
    fragment = fragments.setdefault(index, {"id": "", "name": "", "arguments": ""})
    if tool_call_delta.get("id"):
        fragment["id"] = tool_call_delta["id"]
    function = tool_call_delta.get("function") or {}
    if function.get("name"):
        fragment["name"] = function["name"]
    if function.get("arguments"):
        fragment["arguments"] += function["arguments"]


def get_openrouter_client() -> OpenRouterClientInterface:
    return _HttpxOpenRouterClient(openrouter_settings)
