"""Bounded tool-execution loop for a single chat turn.

Consumes `OpenRouterClientInterface.create_chat_completion`'s live chunk
stream, forwarding reasoning/content deltas as they arrive while also
aggregating each iteration into a `ChatCompletionResult`, validating and
dispatching any requested tool calls against the `tool_registry` passed in
at construction, and re-sending the conversation with the tool results
appended -- up to `MAX_ITERATIONS` iterations.

`tool_registry` is supplied by the caller rather than read from a module
global, because a dependency-bound tool's handler (e.g. `get_team_analysis`,
bound to a request-scoped `AsyncSession`) only exists once a request is in
flight -- see `domain.chat.tools.registry.build_tool_registry`.

`run` is an async generator so a caller (`ChatService`) can forward live
deltas to the browser as they happen instead of waiting for one aggregated
result. It yields `ReasoningDeltaEvent`/`ContentDeltaEvent` as chunks arrive,
`ToolCallRequestedEvent` when a tool call is about to be dispatched,
`WidgetReadyEvent` the moment a widget-producing tool call resolves (well
before the model's final text finishes streaming), and exactly one terminal
`TurnResolvedEvent` (never raised, never discarded) carrying either a
`ChatCompletionResult` or a `ToolLoopCapReached`, plus every `ToolWidgetResult`
collected across the whole turn, once the loop resolves or hits its
iteration cap.

Never raises on a malformed tool call or on hitting the cap: both are
handled as data (a `role: "tool"` error message fed back to the model, or a
`ToolLoopCapReached` result inside the terminal event) so the caller always
has something to show the user.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import ValidationError

from src.domain.chat.tools.registry import ToolDefinition
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.openrouter.schemas import (
    ChatCompletionChunk,
    ChatCompletionResult,
    FinishReason,
    ToolCall,
    ToolLoopCapReached,
)

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

CLARIFICATION_REQUEST = (
    "I wasn't able to fully resolve this with the available tools after "
    "several attempts -- could you clarify what you're looking for?"
)


@dataclass(frozen=True)
class ReasoningDeltaEvent:
    """One incremental piece of the model's reasoning trace."""

    content: str


@dataclass(frozen=True)
class ContentDeltaEvent:
    """One incremental piece of the model's final-answer content."""

    content: str


@dataclass(frozen=True)
class ToolCallRequestedEvent:
    """The loop is about to validate and dispatch a requested tool call."""

    name: str


@dataclass(frozen=True)
class ToolWidgetResult:
    """One widget-producing tool call's resolved data, tagged with the
    `tool_call_id` that requested it and the `widget_type` its
    `ToolDefinition` declares (e.g. `"team_widget"`).
    """

    tool_call_id: str
    tool_name: str
    widget_type: str
    data: dict


@dataclass(frozen=True)
class WidgetReadyEvent:
    """Live signal that a widget-producing tool call resolved -- yielded
    immediately, inside the loop, so a caller can forward it to the
    frontend well before the model's final text starts streaming (which
    only happens on the *next* iteration, after the model has read this
    tool's result). The same `widget` also lands in the terminal
    `TurnResolvedEvent.content_segments`, at the position it actually
    occurred, for a full-message reconstruction.
    """

    widget: ToolWidgetResult


@dataclass(frozen=True)
class TurnResolvedEvent:
    """Terminal event for one full chat turn.

    `result` is a `ChatCompletionResult` on a normal completion, or a
    `ToolLoopCapReached` when the iteration cap tripped without a final
    answer.

    `content_segments` is the turn's text and widgets in the order they
    actually occurred -- one string per iteration that produced content,
    interleaved with a `ToolWidgetResult` right after the tool call that
    produced it. This mirrors exactly how the frontend already builds
    `parts` live (text before a widget, the widget, text after), so a
    caller building the final message from this list -- instead of putting
    all text first and appending every widget after -- doesn't make the
    widget jump position once the turn resolves. A tool called more than
    once in one turn (e.g. comparing two teams) contributes one entry per
    call, never collapsed.
    """

    result: ChatCompletionResult | ToolLoopCapReached
    content_segments: list[str | ToolWidgetResult] = field(default_factory=list)


ToolLoopEvent = (
    ReasoningDeltaEvent
    | ContentDeltaEvent
    | ToolCallRequestedEvent
    | WidgetReadyEvent
    | TurnResolvedEvent
)


class ToolCallExecutor:
    """Runs the bounded tool-execution loop for one chat turn."""

    def __init__(
        self,
        openrouter_client: OpenRouterClientInterface,
        tool_registry: dict[str, ToolDefinition],
    ) -> None:
        self._openrouter_client = openrouter_client
        self._tool_registry = tool_registry

    async def run(
        self, completion_messages: list[dict], tools: list[dict]
    ) -> AsyncIterator[ToolLoopEvent]:
        """Mutates `completion_messages` in place, appending the assistant's
        tool-call requests and the tool results as the loop iterates.
        """
        # Every iteration's content (if any) becomes one segment, followed by
        # a segment for each widget-producing tool call it triggered -- true
        # chronological order, not "all text, then every widget."
        content_segments: list[str | ToolWidgetResult] = []

        for _iteration in range(MAX_ITERATIONS):
            chunks = self._openrouter_client.create_chat_completion(
                messages=completion_messages, tools=tools
            )
            aggregator = _ChunkAggregator()
            async for chunk in chunks:
                if chunk.delta_reasoning:
                    yield ReasoningDeltaEvent(content=chunk.delta_reasoning)
                if chunk.delta_content:
                    yield ContentDeltaEvent(content=chunk.delta_content)
                aggregator.absorb(chunk)
            result = aggregator.finalize()

            if result.content:
                content_segments.append(result.content)

            if result.finish_reason != "tool_calls" or not result.tool_calls:
                yield TurnResolvedEvent(result=result, content_segments=content_segments)
                return

            completion_messages.append(_assistant_tool_call_message(result))
            for tool_call in result.tool_calls:
                yield ToolCallRequestedEvent(name=tool_call.name)
                tool_message, widget_result = await self._execute_tool_call(tool_call)
                completion_messages.append(tool_message)
                if widget_result is not None:
                    content_segments.append(widget_result)
                    yield WidgetReadyEvent(widget=widget_result)

        logger.info("Tool-execution loop hit the %s-iteration cap", MAX_ITERATIONS)
        partial_content = "".join(s for s in content_segments if isinstance(s, str))
        yield TurnResolvedEvent(
            result=ToolLoopCapReached(
                partial_content=partial_content,
                clarification=CLARIFICATION_REQUEST,
            ),
            content_segments=content_segments,
        )

    async def _execute_tool_call(self, tool_call: ToolCall) -> tuple[dict, ToolWidgetResult | None]:
        tool_definition = self._tool_registry.get(tool_call.name)
        if tool_definition is None:
            logger.info("Rejected unknown tool call name=%s", tool_call.name)
            return _tool_result_message(tool_call, f"Unknown tool '{tool_call.name}'."), None

        try:
            args = tool_definition.args_model.model_validate_json(tool_call.arguments or "{}")
        except ValidationError as exc:
            logger.info("Rejected invalid arguments for tool=%s: %s", tool_call.name, exc)
            return (
                _tool_result_message(tool_call, f"Invalid arguments for '{tool_call.name}': {exc}"),
                None,
            )

        execution = await tool_definition.handler(args)
        tool_message = _tool_result_message(tool_call, execution.content)

        if execution.widget_data is None or tool_definition.widget_type is None:
            return tool_message, None

        widget_result = ToolWidgetResult(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            widget_type=tool_definition.widget_type,
            data=execution.widget_data,
        )
        return tool_message, widget_result


def _assistant_tool_call_message(result: ChatCompletionResult) -> dict:
    return {
        "role": "assistant",
        "content": result.content or None,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {"name": tool_call.name, "arguments": tool_call.arguments},
            }
            for tool_call in result.tool_calls
        ],
    }


def _tool_result_message(tool_call: ToolCall, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.name,
        "content": content,
    }


class _ChunkAggregator:
    """Accumulates one turn's live chunk stream into a `ChatCompletionResult`
    while the caller simultaneously forwards each chunk's deltas onward.
    """

    def __init__(self) -> None:
        self._content_parts: list[str] = []
        self._reasoning_parts: list[str] = []
        self._tool_calls: list[ToolCall] = []
        self._finish_reason: FinishReason | None = None
        self._model: str | None = None

    def absorb(self, chunk: ChatCompletionChunk) -> None:
        if chunk.delta_content:
            self._content_parts.append(chunk.delta_content)
        if chunk.delta_reasoning:
            self._reasoning_parts.append(chunk.delta_reasoning)
        if chunk.tool_calls is not None:
            self._tool_calls = chunk.tool_calls
        if chunk.finish_reason is not None:
            self._finish_reason = chunk.finish_reason
        if chunk.model is not None:
            self._model = chunk.model

    def finalize(self) -> ChatCompletionResult:
        if self._finish_reason is None or self._model is None:
            raise OpenRouterRequestFailed(None, "Unexpected response shape")

        return ChatCompletionResult(
            content="".join(self._content_parts),
            reasoning="".join(self._reasoning_parts),
            tool_calls=self._tool_calls,
            finish_reason=self._finish_reason,
            model=self._model,
        )
