"""Integration tests for `ToolCallExecutor`.

Per AGENTS.md's testing guidance, these drive the real `ToolCallExecutor`
against real fake `OpenRouterClientInterface` implementations (no
`Mock()`/`@patch`) and the real `GetCurrentUtcTimeArgs` Pydantic model from
`domain.chat.tools.registry.STATIC_TOOL_REGISTRY` -- no fake tool schemas.

`ToolCallExecutor.run` is an async generator: it forwards live
`ReasoningDeltaEvent`/`ContentDeltaEvent` chunks as they arrive and dispatches
`ToolCallRequestedEvent` before each tool call, always ending with exactly one
`TurnResolvedEvent` carrying the loop's final result. These tests drain the
generator and assert on the collected events.
"""

from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel, ConfigDict

from src.domain.chat.services.tool_call_executor import (
    CLARIFICATION_REQUEST,
    MAX_ITERATIONS,
    ContentDeltaEvent,
    ToolCallExecutor,
    ToolCallRequestedEvent,
    TurnResolvedEvent,
    WidgetReadyEvent,
)
from src.domain.chat.tools.registry import STATIC_TOOL_REGISTRY, ToolDefinition
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.infra.openrouter.schemas import (
    ChatCompletionChunk,
    ChatCompletionResult,
    ToolCall,
    ToolLoopCapReached,
)

_TOOLS = [tool_definition.json_schema for tool_definition in STATIC_TOOL_REGISTRY.values()]


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
    executor = ToolCallExecutor(client, STATIC_TOOL_REGISTRY)

    events = [event async for event in executor.run([{"role": "user", "content": "Hi"}], _TOOLS)]

    content_deltas = [e for e in events if isinstance(e, ContentDeltaEvent)]
    assert [e.content for e in content_deltas] == ["Hello there!"]

    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    assert isinstance(terminal.result, ChatCompletionResult)
    assert terminal.result.content == "Hello there!"
    assert terminal.result.finish_reason == "stop"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_tool_call_triggers_executes_and_resolves_final_answer() -> None:
    client = _ScriptedOpenRouterClient(
        [
            _tool_call_chunk(tool_id="call-1", name="get_current_utc_time", arguments="{}"),
            _stop_chunk("It is currently 2026-01-01T00:00:00+00:00."),
        ]
    )
    executor = ToolCallExecutor(client, STATIC_TOOL_REGISTRY)

    events = [
        event
        async for event in executor.run([{"role": "user", "content": "What time is it?"}], _TOOLS)
    ]

    tool_call_events = [e for e in events if isinstance(e, ToolCallRequestedEvent)]
    assert [e.name for e in tool_call_events] == ["get_current_utc_time"]

    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    assert isinstance(terminal.result, ChatCompletionResult)
    assert terminal.result.finish_reason == "stop"
    assert "currently" in terminal.result.content
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
    executor = ToolCallExecutor(client, STATIC_TOOL_REGISTRY)

    events = [
        event
        async for event in executor.run([{"role": "user", "content": "What time is it?"}], _TOOLS)
    ]

    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    assert isinstance(terminal.result, ChatCompletionResult)
    assert terminal.result.finish_reason == "stop"
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
    executor = ToolCallExecutor(client, STATIC_TOOL_REGISTRY)

    events = [
        event async for event in executor.run([{"role": "user", "content": "Loop forever"}], _TOOLS)
    ]

    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    result = terminal.result
    assert isinstance(result, ToolLoopCapReached)
    assert result.clarification == CLARIFICATION_REQUEST
    # Best-effort partial content accumulated across iterations is surfaced,
    # never silently discarded and never replaced by a raw error.
    assert "Checking (attempt 0)..." in result.partial_content
    assert "Checking (attempt 4)..." in result.partial_content
    assert len(client.calls) == MAX_ITERATIONS


class _GetFakeWidgetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


async def _fake_widget_handler(args: _GetFakeWidgetArgs) -> ToolExecutionResult:
    return ToolExecutionResult(
        content=f'{{"name": "{args.name}"}}', widget_data={"name": args.name}
    )


_WIDGET_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_fake_widget",
        "description": "Fake widget-producing tool for executor tests.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

_REGISTRY_WITH_WIDGET_TOOL = {
    **STATIC_TOOL_REGISTRY,
    "get_fake_widget": ToolDefinition(
        json_schema=_WIDGET_TOOL_SCHEMA,
        args_model=_GetFakeWidgetArgs,
        handler=_fake_widget_handler,
        widget_type="fake_widget",
    ),
}
_TOOLS_WITH_WIDGET = [d.json_schema for d in _REGISTRY_WITH_WIDGET_TOOL.values()]


@pytest.mark.asyncio
async def test_widget_producing_tool_call_yields_live_event_and_terminal_result() -> None:
    client = _ScriptedOpenRouterClient(
        [
            _tool_call_chunk(
                tool_id="call-1", name="get_fake_widget", arguments='{"name": "Argentina"}'
            ),
            _stop_chunk("Here's Argentina."),
        ]
    )
    executor = ToolCallExecutor(client, _REGISTRY_WITH_WIDGET_TOOL)

    events = [
        event
        async for event in executor.run(
            [{"role": "user", "content": "Tell me about Argentina"}], _TOOLS_WITH_WIDGET
        )
    ]

    widget_events = [e for e in events if isinstance(e, WidgetReadyEvent)]
    assert len(widget_events) == 1
    assert widget_events[0].widget.tool_call_id == "call-1"
    assert widget_events[0].widget.tool_name == "get_fake_widget"
    assert widget_events[0].widget.widget_type == "fake_widget"
    assert widget_events[0].widget.data == {"name": "Argentina"}

    # The live event is yielded before the final content delta -- the
    # frontend gets the widget without waiting for the rest of the turn.
    tool_call_index = events.index(widget_events[0])
    final_content_index = next(i for i, e in enumerate(events) if isinstance(e, ContentDeltaEvent))
    assert tool_call_index < final_content_index

    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    assert terminal.widget_results == [widget_events[0].widget]


@pytest.mark.asyncio
async def test_same_widget_tool_called_twice_produces_two_separate_results() -> None:
    client = _ScriptedOpenRouterClient(
        [
            _tool_call_chunk(
                tool_id="call-1", name="get_fake_widget", arguments='{"name": "Argentina"}'
            ),
            _tool_call_chunk(
                tool_id="call-2", name="get_fake_widget", arguments='{"name": "Brazil"}'
            ),
            _stop_chunk("Here's both."),
        ]
    )
    executor = ToolCallExecutor(client, _REGISTRY_WITH_WIDGET_TOOL)

    events = [
        event
        async for event in executor.run(
            [{"role": "user", "content": "Compare Argentina and Brazil"}], _TOOLS_WITH_WIDGET
        )
    ]

    widget_events = [e for e in events if isinstance(e, WidgetReadyEvent)]
    assert [e.widget.data["name"] for e in widget_events] == ["Argentina", "Brazil"]

    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    assert [w.data["name"] for w in terminal.widget_results] == ["Argentina", "Brazil"]


@pytest.mark.asyncio
async def test_dummy_tool_never_yields_a_widget_event() -> None:
    client = _ScriptedOpenRouterClient(
        [
            _tool_call_chunk(tool_id="call-1", name="get_current_utc_time", arguments="{}"),
            _stop_chunk("It is currently 2026-01-01T00:00:00+00:00."),
        ]
    )
    executor = ToolCallExecutor(client, STATIC_TOOL_REGISTRY)

    events = [
        event
        async for event in executor.run([{"role": "user", "content": "What time is it?"}], _TOOLS)
    ]

    assert not [e for e in events if isinstance(e, WidgetReadyEvent)]
    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    assert terminal.widget_results == []
