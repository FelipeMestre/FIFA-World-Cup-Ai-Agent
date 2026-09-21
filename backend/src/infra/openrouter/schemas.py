"""Wire-level and aggregate result shapes for the OpenRouter chat client.

`ChatCompletionChunk` is the structured value `_HttpxOpenRouterClient.
create_chat_completion` yields live, chunk by chunk, as OpenRouter's SSE
stream is parsed. `ChatCompletionResult` is an aggregated view built by a
caller that consumes the full chunk stream (see `chat_service.py`'s
aggregation helper); the client itself never returns it directly.
`ChatStreamEventType` and `ToolLoopCapReached` are shared shapes for the
tool-execution loop and SSE router wiring added in later phases of this
change -- defined here now so downstream phases share one source of truth.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

FinishReason = Literal["stop", "tool_calls", "length", "content_filter"]


class ChatStreamEventType(StrEnum):
    """SSE event vocabulary emitted by our own `/chat/messages` endpoint."""

    REASONING_DELTA = "reasoning_delta"
    CONTENT_DELTA = "content_delta"
    TOOL_CALL = "tool_call"
    WIDGET_READY = "widget_ready"
    CAP_REACHED = "cap_reached"
    MESSAGE_DONE = "message_done"
    ERROR = "error"


class ToolCall(BaseModel):
    """One fully-assembled tool call requested by the model."""

    id: str
    name: str
    arguments: str


class ChatCompletionChunk(BaseModel):
    """One incremental piece of an in-flight OpenRouter completion, yielded
    live by `_HttpxOpenRouterClient.create_chat_completion` as OpenRouter's
    SSE stream is parsed. `tool_calls`, `finish_reason`, `cached_tokens`, and
    `cache_write_tokens` are only populated on the final chunk of a turn.
    """

    delta_content: str | None = None
    delta_reasoning: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: FinishReason | None = None
    model: str | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None


class ChatCompletionResult(BaseModel):
    """Aggregated view of a fully-drained `ChatCompletionChunk` stream.

    Built by a caller (e.g. `chat_service.py`'s aggregation helper, or
    PR2's tool-execution loop) that consumes `create_chat_completion`'s
    async generator; never returned directly by the client.
    """

    content: str
    reasoning: str
    tool_calls: list[ToolCall]
    finish_reason: FinishReason
    model: str


class ToolLoopCapReached(BaseModel):
    """Returned by the tool-execution loop when its iteration cap trips
    without a final answer. Never raised as an exception -- always returned
    so the caller can surface it as content, not swallow it.
    """

    partial_content: str
    clarification: str
