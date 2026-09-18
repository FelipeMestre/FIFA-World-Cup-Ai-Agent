"""Bounded tool-execution loop for a single chat turn.

Consumes `OpenRouterClientInterface.create_chat_completion`'s live chunk
stream, forwarding reasoning/content deltas as they arrive while also
aggregating each iteration into a `ChatCompletionResult`, validating and
dispatching any requested tool calls against
`domain.chat.tools.registry.TOOL_REGISTRY`, and re-sending the conversation
with the tool results appended -- up to `MAX_ITERATIONS` iterations.

`run` is an async generator so a caller (`ChatService`) can forward live
deltas to the browser as they happen instead of waiting for one aggregated
result. It yields `ReasoningDeltaEvent`/`ContentDeltaEvent` as chunks arrive,
`ToolCallRequestedEvent` when a tool call is about to be dispatched, and
exactly one terminal `TurnResolvedEvent` (never raised, never discarded)
carrying either a `ChatCompletionResult` or a `ToolLoopCapReached` once the
loop resolves or hits its iteration cap.

Never raises on a malformed tool call or on hitting the cap: both are
handled as data (a `role: "tool"` error message fed back to the model, or a
`ToolLoopCapReached` result inside the terminal event) so the caller always
has something to show the user.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import ValidationError

from src.domain.chat.tools.registry import TOOL_REGISTRY
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
class TurnResolvedEvent:
    """Terminal event for one full chat turn.

    `result` is a `ChatCompletionResult` on a normal completion, or a
    `ToolLoopCapReached` when the iteration cap tripped without a final
    answer. Always the last event `run` yields, exactly once.
    """

    result: ChatCompletionResult | ToolLoopCapReached


ToolLoopEvent = ReasoningDeltaEvent | ContentDeltaEvent | ToolCallRequestedEvent | TurnResolvedEvent


class ToolCallExecutor:
    """Runs the bounded tool-execution loop for one chat turn."""

    def __init__(self, openrouter_client: OpenRouterClientInterface) -> None:
        self._openrouter_client = openrouter_client

    async def run(
        self, completion_messages: list[dict], tools: list[dict]
    ) -> AsyncIterator[ToolLoopEvent]:
        """Mutates `completion_messages` in place, appending the assistant's
        tool-call requests and the tool results as the loop iterates.
        """
        partial_content_parts: list[str] = []

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
                partial_content_parts.append(result.content)

            if result.finish_reason != "tool_calls" or not result.tool_calls:
                yield TurnResolvedEvent(result=result)
                return

            completion_messages.append(_assistant_tool_call_message(result))
            for tool_call in result.tool_calls:
                yield ToolCallRequestedEvent(name=tool_call.name)
                completion_messages.append(await self._execute_tool_call(tool_call))

        logger.info("Tool-execution loop hit the %s-iteration cap", MAX_ITERATIONS)
        yield TurnResolvedEvent(
            result=ToolLoopCapReached(
                partial_content="".join(partial_content_parts),
                clarification=CLARIFICATION_REQUEST,
            )
        )

    async def _execute_tool_call(self, tool_call: ToolCall) -> dict:
        tool_definition = TOOL_REGISTRY.get(tool_call.name)
        if tool_definition is None:
            logger.info("Rejected unknown tool call name=%s", tool_call.name)
            return _tool_result_message(tool_call, f"Unknown tool '{tool_call.name}'.")

        try:
            args = tool_definition.args_model.model_validate_json(tool_call.arguments or "{}")
        except ValidationError as exc:
            logger.info("Rejected invalid arguments for tool=%s: %s", tool_call.name, exc)
            return _tool_result_message(
                tool_call, f"Invalid arguments for '{tool_call.name}': {exc}"
            )

        result_content = await tool_definition.handler(args)
        return _tool_result_message(tool_call, result_content)


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
