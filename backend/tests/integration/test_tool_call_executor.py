"""Integration tests for `ToolCallExecutor`.

Per AGENTS.md's testing guidance, these drive the real `ToolCallExecutor`
against real fake `OpenRouterClientInterface` implementations (no
`Mock()`/`@patch`) and the real `GetCurrentUtcTimeArgs` Pydantic model from
`domain.chat.tools.registry.TOOL_REGISTRY` -- no fake tool schemas.
"""

from collections.abc import AsyncIterator

import pytest

from src.domain.chat.services.tool_call_executor import (
    CLARIFICATION_REQUEST,
    MAX_ITERATIONS,
    ToolCallExecutor,
)
from src.domain.chat.tools.registry import TOOL_REGISTRY
from src.infra.openrouter.schemas import (
    ChatCompletionChunk,
    ChatCompletionResult,
    ToolLoopCapReached,
)

_TOOLS = [tool_definition.json_schema for tool_definition in TOOL_REGISTRY.values()]


def _stop_chunk(content: str) -> AsyncIterator[ChatCompletionChunk]:
    async def _gen() -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(delta_content=content)
        yield ChatCompletionChunk(
            finish_reason="stop", model="anthropic/claude-sonnet-4.5", tool_calls=[]
        )

    return _gen()


def _tool_call_chunk(
    *, tool_id: str, name: str, arguments: str, content: str = ""
) -> AsyncIterator[ChatCompletionChunk]:
    async def _gen() -> AsyncIterator[ChatCompletionChunk]:
        from src.infra.openrouter.schemas import ToolCall

        if content:
            yield ChatCompletionChunk(delta_content=content)
        yield ChatCompletionChunk(
            finish_reason="tool_calls",
            model="anthropic/claude-sonnet-4.5",
            tool_calls=[ToolCall(id=tool_id, name=name, arguments=arguments)],
        )

    return _gen()


class _ScriptedOpenRouterClient:
    """Fake client that returns one scripted response generator per call,
    consumed in order -- proves the loop re-sends the conversation with the
    tool results appended.
    """

    def __init__(self, responses: list[AsyncIterator[ChatCompletionChunk]]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self.calls.append([dict(m) for m in messages])
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_plain_message_returns_result_without_tool_calls() -> None:
    client = _ScriptedOpenRouterClient([_stop_chunk("Hello there!")])
    executor = ToolCallExecutor(client)

    result = await executor.run([{"role": "user", "content": "Hi"}], _TOOLS)

    assert isinstance(result, ChatCompletionResult)
    assert result.content == "Hello there!"
    assert result.finish_reason == "stop"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_tool_call_triggers_executes_and_resolves_final_answer() -> None:
    client = _ScriptedOpenRouterClient(
        [
            _tool_call_chunk(tool_id="call-1", name="get_current_utc_time", arguments="{}"),
            _stop_chunk("It is currently 2026-01-01T00:00:00+00:00."),
        ]
    )
    executor = ToolCallExecutor(client)

    result = await executor.run([{"role": "user", "content": "What time is it?"}], _TOOLS)

    assert isinstance(result, ChatCompletionResult)
    assert result.finish_reason == "stop"
    assert "currently" in result.content
    assert len(client.calls) == 2

    # Second call's messages include the assistant tool-call request and the
    # tool result appended by the executor.
    second_call_messages = client.calls[1]
    assert second_call_messages[-2]["role"] == "assistant"
    assert second_call_messages[-2]["tool_calls"][0]["function"]["name"] == ("get_current_utc_time")
    tool_message = second_call_messages[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert tool_message["name"] == "get_current_utc_time"
    # Real handler output: an ISO-8601 UTC timestamp, not a placeholder.
    assert tool_message["content"].endswith("+00:00")


@pytest.mark.asyncio
async def test_invalid_tool_call_arguments_rejected_without_crashing() -> None:
    client = _ScriptedOpenRouterClient(
        [
            _tool_call_chunk(
                tool_id="call-1",
                name="get_current_utc_time",
                arguments='{"unexpected_field": "boom"}',
            ),
            _stop_chunk("Sorry, I couldn't use that tool correctly."),
        ]
    )
    executor = ToolCallExecutor(client)

    result = await executor.run([{"role": "user", "content": "What time is it?"}], _TOOLS)

    assert isinstance(result, ChatCompletionResult)
    assert result.finish_reason == "stop"
    assert len(client.calls) == 2

    tool_message = client.calls[1][-1]
    assert tool_message["role"] == "tool"
    assert "Invalid arguments" in tool_message["content"]


@pytest.mark.asyncio
async def test_iteration_cap_returns_partial_content_and_clarification() -> None:
    responses = [
        _tool_call_chunk(
            tool_id=f"call-{i}",
            name="get_current_utc_time",
            arguments="{}",
            content=f"Checking (attempt {i})... ",
        )
        for i in range(MAX_ITERATIONS)
    ]
    client = _ScriptedOpenRouterClient(responses)
    executor = ToolCallExecutor(client)

    result = await executor.run([{"role": "user", "content": "Loop forever"}], _TOOLS)

    assert isinstance(result, ToolLoopCapReached)
    assert result.clarification == CLARIFICATION_REQUEST
    # Best-effort partial content accumulated across iterations is surfaced,
    # never silently discarded and never replaced by a raw error.
    assert "Checking (attempt 0)..." in result.partial_content
    assert "Checking (attempt 4)..." in result.partial_content
    assert len(client.calls) == MAX_ITERATIONS
