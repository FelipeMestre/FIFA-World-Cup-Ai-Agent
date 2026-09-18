"""Bounded tool-execution loop for a single chat turn.

Consumes `OpenRouterClientInterface.create_chat_completion`'s live chunk
stream, aggregates it into one `ChatCompletionResult` per iteration,
validates and dispatches any requested tool calls against
`domain.chat.tools.registry.TOOL_REGISTRY`, and re-sends the conversation
with the tool results appended -- up to `MAX_ITERATIONS` iterations.

Never raises on a malformed tool call or on hitting the cap: both are
returned as data (a `role: "tool"` error message fed back to the model, or a
`ToolLoopCapReached` result) so the caller always has something to show the
user. This is the loop's own per-iteration aggregation, superseding PR1's
interim `_aggregate_chat_completion` helper that used to live in
`chat_service.py`.
"""

import logging
from collections.abc import AsyncIterator

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


class ToolCallExecutor:
    """Runs the bounded tool-execution loop for one chat turn."""

    def __init__(self, openrouter_client: OpenRouterClientInterface) -> None:
        self._openrouter_client = openrouter_client

    async def run(
        self, completion_messages: list[dict], tools: list[dict]
    ) -> ChatCompletionResult | ToolLoopCapReached:
        """Mutates `completion_messages` in place, appending the assistant's
        tool-call requests and the tool results as the loop iterates.
        """
        partial_content_parts: list[str] = []

        for _iteration in range(MAX_ITERATIONS):
            chunks = self._openrouter_client.create_chat_completion(
                messages=completion_messages, tools=tools
            )
            result = await _aggregate_chat_completion(chunks)

            if result.content:
                partial_content_parts.append(result.content)

            if result.finish_reason != "tool_calls" or not result.tool_calls:
                return result

            completion_messages.append(_assistant_tool_call_message(result))
            for tool_call in result.tool_calls:
                completion_messages.append(await self._execute_tool_call(tool_call))

        logger.info("Tool-execution loop hit the %s-iteration cap", MAX_ITERATIONS)
        return ToolLoopCapReached(
            partial_content="".join(partial_content_parts),
            clarification=CLARIFICATION_REQUEST,
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


async def _aggregate_chat_completion(
    chunks: AsyncIterator[ChatCompletionChunk],
) -> ChatCompletionResult:
    """Consume one full turn's live chunk stream into one aggregated result."""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    finish_reason: FinishReason | None = None
    model: str | None = None

    async for chunk in chunks:
        if chunk.delta_content:
            content_parts.append(chunk.delta_content)
        if chunk.delta_reasoning:
            reasoning_parts.append(chunk.delta_reasoning)
        if chunk.tool_calls is not None:
            tool_calls = chunk.tool_calls
        if chunk.finish_reason is not None:
            finish_reason = chunk.finish_reason
        if chunk.model is not None:
            model = chunk.model

    if finish_reason is None or model is None:
        raise OpenRouterRequestFailed(None, "Unexpected response shape")

    return ChatCompletionResult(
        content="".join(content_parts),
        reasoning="".join(reasoning_parts),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        model=model,
    )
