"""Chat-turn event vocabulary and its Redis-stream (de)serialization -- split
out of `chat_service.py` purely to keep both files under this repo's
400-line-per-file cap (`CLAUDE.md`), the same reasoning `chat_streams.py`'s
own module docstring gives for its split from `chat_tasks.py`. Neither file
owns a materially different concept: `chat_service.py` keeps the
`ChatService` class that produces these events; this module owns what they
look like and how they cross a Redis Stream (`XADD` values must be strings,
so every event is flattened to an `event_type` + JSON `payload` pair of
fields). Living here also lets `chat_streams.py` and `sse.py` import this
vocabulary without importing `chat_service.py` itself, which would otherwise
be a circular import (`chat_streams.py` is itself imported by
`ChatService.start_turn` to publish `ConversationCreatedEvent`).
"""

from dataclasses import dataclass

from src.domain.chat.services.tool_call_executor import (
    ContentDeltaEvent,
    ReasoningDeltaEvent,
    ToolCallRequestedEvent,
    ToolWidgetResult,
    WidgetReadyEvent,
)


@dataclass(frozen=True)
class CapReachedEvent:
    """The tool-execution loop's iteration cap tripped. `content` is the
    best-effort partial content accumulated so far; `clarification` is the
    clarification-ask text appended after it. Always followed by a
    `MessageDoneEvent` carrying the same combined text.
    """

    content: str
    clarification: str


@dataclass(frozen=True)
class PersistenceFailedEvent:
    """Non-fatal: the Postgres durable write for this turn (or the
    `conversation.touch()` alongside it) failed. Unlike `ChatServiceUnavailable`
    (which aborts the stream before any content has been sent), this is
    raised *after* the reply has already streamed to the user via
    `content_delta`/`widget_ready` events, so the turn always still finishes
    with a `MessageDoneEvent` -- this event only warns the frontend that the
    just-shown message may not survive a reload. The Redis cache write is
    handled separately and never surfaces here: it is a rebuildable
    read-through cache and its own failure is swallowed silently.
    """

    detail: str


@dataclass(frozen=True)
class MessageDoneEvent:
    """Terminal event for one chat turn: the conversation has been
    persisted and `content` is the final text shown to the user (either the
    assistant's normal reply, or the cap-trip's partial content plus
    clarification).

    `content_segments` is what a full-message render (e.g. the SSE `parts`
    array, or a page reload replaying this message) should actually be
    built from -- text and widgets in the order they occurred, matching
    what was already shown live via `WidgetReadyEvent`. It is *not* just
    `[content, *widgets]`: on a normal completion this is `ToolCallExecutor`'s
    own `content_segments`, preserving true interleaving; on a cap-trip it
    collapses to a single `content` segment (widgets from an incomplete,
    already-degraded turn aren't worth threading through -- the frontend
    ignores these `parts` in that case anyway, keeping its own
    already-rendered content instead).
    """

    conversation_id: str
    content: str
    model: str | None
    content_segments: list[str | ToolWidgetResult]


ChatTurnEvent = (
    ReasoningDeltaEvent
    | ContentDeltaEvent
    | ToolCallRequestedEvent
    | WidgetReadyEvent
    | CapReachedEvent
    | PersistenceFailedEvent
    | MessageDoneEvent
)


def _widget_result_to_dict(widget: ToolWidgetResult) -> dict:
    return {
        "tool_call_id": widget.tool_call_id,
        "tool_name": widget.tool_name,
        "widget_type": widget.widget_type,
        "data": widget.data,
    }


def _widget_result_from_dict(widget: dict) -> ToolWidgetResult:
    return ToolWidgetResult(
        tool_call_id=widget["tool_call_id"],
        tool_name=widget["tool_name"],
        widget_type=widget["widget_type"],
        data=widget["data"],
    )


def _segment_to_dict(segment: str | ToolWidgetResult) -> dict:
    if isinstance(segment, str):
        return {"kind": "text", "content": segment}
    return {"kind": "widget", **_widget_result_to_dict(segment)}


def _segment_from_dict(segment: dict) -> str | ToolWidgetResult:
    if segment["kind"] == "text":
        return segment["content"]
    return _widget_result_from_dict(segment)


def chat_turn_event_payload(event: ChatTurnEvent) -> tuple[str, dict]:
    """Maps one `ChatTurnEvent` to the Redis turn-stream shape.

    Returns `(event_type, payload)`. `event_type` is the dataclass name.
    `payload` is JSON-safe but not encoded -- the caller that writes the
    stream (`XADD` values must be strings) encodes it.
    """
    if isinstance(event, (ReasoningDeltaEvent, ContentDeltaEvent)):
        payload = {"content": event.content}
    elif isinstance(event, ToolCallRequestedEvent):
        payload = {"name": event.name}
    elif isinstance(event, WidgetReadyEvent):
        payload = {"widget": _widget_result_to_dict(event.widget)}
    elif isinstance(event, CapReachedEvent):
        payload = {"content": event.content, "clarification": event.clarification}
    elif isinstance(event, PersistenceFailedEvent):
        payload = {"detail": event.detail}
    elif isinstance(event, MessageDoneEvent):
        payload = {
            "conversation_id": event.conversation_id,
            "content": event.content,
            "model": event.model,
            "content_segments": [_segment_to_dict(segment) for segment in event.content_segments],
        }
    else:
        raise ValueError(f"Unhandled chat stream event: {event!r}")
    return type(event).__name__, payload


def parse_chat_turn_event(event_type: str, payload: dict) -> ChatTurnEvent | None:
    """Inverse of `chat_turn_event_payload`.

    Returns None when `event_type` is not a domain event -- the job publishes
    its own failure tags (an exception class name) on the same stream.
    """
    if event_type == "ReasoningDeltaEvent":
        return ReasoningDeltaEvent(content=payload["content"])
    if event_type == "ContentDeltaEvent":
        return ContentDeltaEvent(content=payload["content"])
    if event_type == "ToolCallRequestedEvent":
        return ToolCallRequestedEvent(name=payload["name"])
    if event_type == "WidgetReadyEvent":
        return WidgetReadyEvent(widget=_widget_result_from_dict(payload["widget"]))
    if event_type == "CapReachedEvent":
        return CapReachedEvent(content=payload["content"], clarification=payload["clarification"])
    if event_type == "PersistenceFailedEvent":
        return PersistenceFailedEvent(detail=payload["detail"])
    if event_type == "MessageDoneEvent":
        return MessageDoneEvent(
            conversation_id=payload["conversation_id"],
            content=payload["content"],
            model=payload["model"],
            content_segments=[
                _segment_from_dict(segment) for segment in payload["content_segments"]
            ],
        )
    return None
