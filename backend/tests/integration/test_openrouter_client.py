"""Integration tests for `_HttpxOpenRouterClient`.

Per AGENTS.md's testing guidance, these exercise the real client against
`httpx.MockTransport` (httpx's own test transport, not a generic mock
library) serving a recorded-style OpenRouter SSE fixture -- no `Mock()`/
`@patch`, real request/response bytes. `create_chat_completion` is an async
generator, so every test drives it by iterating (`async for`/list
comprehension) rather than awaiting a single return value.
"""

import json

import httpx
import pytest

from src.infra.openrouter.client import _HttpxOpenRouterClient
from src.infra.openrouter.config import OpenRouterConfig
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.schemas import ChatCompletionChunk

_PLAIN_MESSAGE_SSE_FIXTURE = (
    'data: {"id":"gen-1","model":"anthropic/claude-sonnet-4.5",'
    '"choices":[{"index":0,"delta":{"role":"assistant","content":""},'
    '"finish_reason":null}]}\n\n'
    'data: {"id":"gen-1","model":"anthropic/claude-sonnet-4.5",'
    '"choices":[{"index":0,"delta":{"content":"Hello"},'
    '"finish_reason":null}]}\n\n'
    'data: {"id":"gen-1","model":"anthropic/claude-sonnet-4.5",'
    '"choices":[{"index":0,"delta":{"content":", world!"},'
    '"finish_reason":null}]}\n\n'
    'data: {"id":"gen-1","model":"anthropic/claude-sonnet-4.5",'
    '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],'
    '"usage":{"prompt_tokens_details":{"cached_tokens":128},'
    '"cache_write_tokens":0}}\n\n'
    "data: [DONE]\n\n"
)


def _config(**overrides: object) -> OpenRouterConfig:
    defaults: dict = {
        "API_KEY": "test-key",
        "MODELS": ["anthropic/claude-sonnet-4.5", "openai/gpt-4.1"],
    }
    defaults.update(overrides)
    return OpenRouterConfig(**defaults)


def _aggregate_content(chunks: list[ChatCompletionChunk]) -> str:
    return "".join(chunk.delta_content for chunk in chunks if chunk.delta_content)


@pytest.mark.asyncio
async def test_plain_message_round_trips_through_yielded_chunks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_PLAIN_MESSAGE_SSE_FIXTURE,
            headers={"content-type": "text/event-stream"},
        )

    client = _HttpxOpenRouterClient(_config(), transport=httpx.MockTransport(handler))

    chunks = [
        chunk
        async for chunk in client.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello"},
            ]
        )
    ]

    assert _aggregate_content(chunks) == "Hello, world!"
    final_chunk = chunks[-1]
    assert final_chunk.finish_reason == "stop"
    assert final_chunk.model == "anthropic/claude-sonnet-4.5"
    assert final_chunk.tool_calls == []


@pytest.mark.asyncio
async def test_chunks_are_yielded_incrementally_not_aggregated() -> None:
    """Proves `create_chat_completion` yields chunk-by-chunk as it parses,
    rather than accumulating internally and returning one combined result:
    the two content deltas from the fixture must arrive as two distinct
    chunks, neither of which carries the full aggregated text.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_PLAIN_MESSAGE_SSE_FIXTURE,
            headers={"content-type": "text/event-stream"},
        )

    client = _HttpxOpenRouterClient(_config(), transport=httpx.MockTransport(handler))

    content_chunks: list[ChatCompletionChunk] = []
    async for chunk in client.create_chat_completion(
        messages=[{"role": "user", "content": "Say hello"}]
    ):
        if chunk.delta_content:
            content_chunks.append(chunk)

    assert [chunk.delta_content for chunk in content_chunks] == ["Hello", ", world!"]
    for chunk in content_chunks:
        assert chunk.delta_content != "Hello, world!"


@pytest.mark.asyncio
async def test_models_fallback_list_sent_in_priority_order() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(
            200,
            content=_PLAIN_MESSAGE_SSE_FIXTURE,
            headers={"content-type": "text/event-stream"},
        )

    config = _config(MODELS=["anthropic/claude-sonnet-4.5", "openai/gpt-4.1", "meta/llama-3.3"])
    client = _HttpxOpenRouterClient(config, transport=httpx.MockTransport(handler))

    async for _ in client.create_chat_completion(messages=[{"role": "user", "content": "Hi"}]):
        pass

    sent_body = json.loads(captured["body"])
    assert sent_body["models"] == [
        "anthropic/claude-sonnet-4.5",
        "openai/gpt-4.1",
        "meta/llama-3.3",
    ]
    assert "model" not in sent_body


@pytest.mark.asyncio
async def test_system_message_gets_ephemeral_cache_control_block() -> None:
    captured: dict = {}
    disclaimer = (
        "IMPORTANT: the underlying tournament dataset is a simulated, "
        "synthetic FIFA World Cup 2026 -- not a record of real-world results."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(
            200,
            content=_PLAIN_MESSAGE_SSE_FIXTURE,
            headers={"content-type": "text/event-stream"},
        )

    client = _HttpxOpenRouterClient(_config(), transport=httpx.MockTransport(handler))

    async for _ in client.create_chat_completion(
        messages=[
            {"role": "system", "content": disclaimer},
            {"role": "user", "content": "Hi"},
        ]
    ):
        pass

    sent_body = json.loads(captured["body"])
    system_content = sent_body["messages"][0]["content"]
    assert isinstance(system_content, list)
    assert system_content[0]["type"] == "text"
    assert system_content[0]["text"] == disclaimer
    assert system_content[0]["cache_control"] == {"type": "ephemeral"}
    # Non-system messages are untouched plain-string content.
    assert sent_body["messages"][1]["content"] == "Hi"


@pytest.mark.asyncio
async def test_non_2xx_response_raises_openrouter_request_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream error")

    client = _HttpxOpenRouterClient(_config(), transport=httpx.MockTransport(handler))

    with pytest.raises(OpenRouterRequestFailed):
        async for _ in client.create_chat_completion(messages=[{"role": "user", "content": "Hi"}]):
            pass
