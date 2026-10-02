"""Helpers shared by the golden tests: call a registry tool, drive the executor."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.domain.chat.services.tool_call_executor import (
    ToolCallExecutor,
    ToolLoopEvent,
    TurnResolvedEvent,
)
from src.domain.chat.tools.registry import ToolDefinition
from src.infra.openrouter.schemas import ChatCompletionChunk, ToolCall

SCRIPTED_MODEL = "golden/scripted-model"


@dataclass(frozen=True)
class ToolOutcome:
    """A handler result with `content` already parsed from JSON."""

    payload: dict
    widget_data: dict | None


async def call_tool(registry: dict[str, ToolDefinition], name: str, **args) -> ToolOutcome:
    """Validate `args` with the tool's own args model, run its handler, parse the JSON."""
    definition = registry[name]
    result = await definition.handler(definition.args_model(**args))
    return ToolOutcome(payload=json.loads(result.content), widget_data=result.widget_data)


def tool_call_response(
    tool_id: str, name: str, arguments: dict | str, content: str = ""
) -> AsyncIterator[ChatCompletionChunk]:
    """One scripted model turn that requests a single tool call."""
    raw_arguments = arguments if isinstance(arguments, str) else json.dumps(arguments)

    async def _chunks() -> AsyncIterator[ChatCompletionChunk]:
        if content:
            yield ChatCompletionChunk(delta_content=content)
        yield ChatCompletionChunk(
            finish_reason="tool_calls",
            model=SCRIPTED_MODEL,
            tool_calls=[ToolCall(id=tool_id, name=name, arguments=raw_arguments)],
        )

    return _chunks()


def final_answer_response(content: str) -> AsyncIterator[ChatCompletionChunk]:
    """One scripted model turn that ends the loop with a plain answer."""

    async def _chunks() -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(delta_content=content)
        yield ChatCompletionChunk(finish_reason="stop", model=SCRIPTED_MODEL, tool_calls=[])

    return _chunks()


class ScriptedOpenRouterClient:
    """Returns one scripted model turn per call, in order, and records the messages it saw."""

    def __init__(self, responses: list[AsyncIterator[ChatCompletionChunk]]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self.calls.append([dict(message) for message in messages])
        return self._responses.pop(0)


async def run_turn(
    registry: dict[str, ToolDefinition], client: ScriptedOpenRouterClient, question: str
) -> list[ToolLoopEvent]:
    """Drain one executor turn against the real registry and scripted model."""
    executor = ToolCallExecutor(client, registry)
    tool_schemas = [definition.json_schema for definition in registry.values()]
    return [
        event async for event in executor.run([{"role": "user", "content": question}], tool_schemas)
    ]


def resolved_turn(events: list[ToolLoopEvent]) -> TurnResolvedEvent:
    terminal = events[-1]
    assert isinstance(terminal, TurnResolvedEvent)
    return terminal
