"""`ChatTurnEvent`/Redis-stream-entry -> SSE wire DTO serialization, shared
between the live chat endpoint (`chat_router.py`) and the watch/reattach
endpoint (`conversation_router.py`) for a background job's turn. Both need
the exact same event -> DTO mapping; this is the one place it lives instead
of drifting into two copies.

`to_dto` converts a live `ChatTurnEvent` (as `chat_router.py`'s own
`send_message` generator yields it). `redis_entry_to_dto` converts one
`chat:turn-stream:{conversation_id}` entry -- the flattened JSON shape
`infra/task_queue/chat_tasks.py`'s `serialize_chat_turn_event` writes, not
a live `ChatTurnEvent` -- into the identical DTO shape, so a reattached
watcher and a live sender see indistinguishable SSE frames. The two
functions duplicate the same field mapping unavoidably: their inputs are
different shapes (a real dataclass vs. plain JSON), so there is no single
object both could operate on.
"""

from src.api.v1.chat.dtos.chat_dtos import (
    WIDGET_TYPE_TO_PART_CLASS,
    CapReachedEventDto,
    ChatStreamEvent,
    ContentDeltaEventDto,
    ErrorEventDto,
    MessageDoneEventDto,
    MessagePart,
    ReasoningDeltaEventDto,
    TextPart,
    ToolCallEventDto,
    WidgetReadyEventDto,
)
from src.domain.chat.services.chat_service import (
    CapReachedEvent,
    ChatTurnEvent,
    ContentDeltaEvent,
    MessageDoneEvent,
    PersistenceFailedEvent,
    ReasoningDeltaEvent,
)
from src.domain.chat.services.tool_call_executor import (
    ToolCallRequestedEvent,
    ToolWidgetResult,
    WidgetReadyEvent,
)

# Event types `generate_chat_reply_task` can still publish *after* this one
# -- everything else (MessageDoneEvent, or one of the job's own ad hoc
# exception-class-name error tags) is terminal: no further entry is ever
# written for that turn once one of those lands.
_NON_TERMINAL_EVENT_TYPES = frozenset(
    {
        "ReasoningDeltaEvent",
        "ContentDeltaEvent",
        "ToolCallRequestedEvent",
        "WidgetReadyEvent",
        "CapReachedEvent",
        "PersistenceFailedEvent",
    }
)


def is_terminal_event_type(event_type: str) -> bool:
    return event_type not in _NON_TERMINAL_EVENT_TYPES


def widget_part(widget: ToolWidgetResult) -> MessagePart:
    part_class = WIDGET_TYPE_TO_PART_CLASS.get(widget.widget_type)
    if part_class is None:
        raise ValueError(f"No MessagePart mapped for widget_type={widget.widget_type!r}")
    return part_class(data=widget.data)


def _segment_to_part(segment: str | ToolWidgetResult) -> MessagePart:
    if isinstance(segment, str):
        return TextPart(content=segment)
    return widget_part(segment)


def to_dto(event: ChatTurnEvent) -> ChatStreamEvent:
    if isinstance(event, ReasoningDeltaEvent):
        return ReasoningDeltaEventDto(content=event.content)
    if isinstance(event, ContentDeltaEvent):
        return ContentDeltaEventDto(content=event.content)
    if isinstance(event, ToolCallRequestedEvent):
        return ToolCallEventDto(name=event.name)
    if isinstance(event, WidgetReadyEvent):
        return WidgetReadyEventDto(part=widget_part(event.widget))
    if isinstance(event, CapReachedEvent):
        return CapReachedEventDto(content=event.content, clarification=event.clarification)
    if isinstance(event, PersistenceFailedEvent):
        # Reuses the existing `error` SSE event vocabulary -- unlike a
        # `ChatServiceUnavailable` (never yielded, only ever raised), this
        # is yielded mid-stream as a non-fatal warning and is always
        # followed by a `message_done` event for the same turn.
        return ErrorEventDto(detail=event.detail)
    if isinstance(event, MessageDoneEvent):
        # `content_segments` already carries text and widgets in the order
        # they occurred (see `MessageDoneEvent`'s docstring) -- never
        # `[all text, *widgets]`, which is what made a widget jump to the
        # bottom once the turn resolved.
        parts = [_segment_to_part(s) for s in event.content_segments] or [
            TextPart(content=event.content)
        ]
        return MessageDoneEventDto(
            conversation_id=event.conversation_id, parts=parts, model=event.model
        )
    raise ValueError(f"Unhandled chat stream event: {event!r}")


def _widget_part_from_dict(widget: dict) -> MessagePart:
    part_class = WIDGET_TYPE_TO_PART_CLASS.get(widget["widget_type"])
    if part_class is None:
        raise ValueError(f"No MessagePart mapped for widget_type={widget['widget_type']!r}")
    return part_class(data=widget["data"])


def _segment_dict_to_part(segment: dict) -> MessagePart:
    if segment["kind"] == "text":
        return TextPart(content=segment["content"])
    return _widget_part_from_dict(segment)


def redis_entry_to_dto(event_type: str, payload: dict) -> ChatStreamEvent:
    if event_type == "ReasoningDeltaEvent":
        return ReasoningDeltaEventDto(content=payload["content"])
    if event_type == "ContentDeltaEvent":
        return ContentDeltaEventDto(content=payload["content"])
    if event_type == "ToolCallRequestedEvent":
        return ToolCallEventDto(name=payload["name"])
    if event_type == "WidgetReadyEvent":
        return WidgetReadyEventDto(part=_widget_part_from_dict(payload["widget"]))
    if event_type == "CapReachedEvent":
        return CapReachedEventDto(
            content=payload["content"], clarification=payload["clarification"]
        )
    if event_type == "PersistenceFailedEvent":
        return ErrorEventDto(detail=payload["detail"])
    if event_type == "MessageDoneEvent":
        parts = [_segment_dict_to_part(s) for s in payload["content_segments"]] or [
            TextPart(content=payload["content"])
        ]
        return MessageDoneEventDto(
            conversation_id=payload["conversation_id"], parts=parts, model=payload["model"]
        )
    # Any other tag is one of the job's own ad hoc failure markers (an
    # exception class name, e.g. "ChatServiceUnavailable" or "RuntimeError")
    # -- not a domain ChatTurnEvent at all, just "something went wrong, and
    # here is why", reusing the same `error` SSE vocabulary either way.
    return ErrorEventDto(detail=payload.get("detail", event_type))


def format_sse(dto: ChatStreamEvent) -> bytes:
    payload = dto.model_dump_json(exclude={"type"})
    return f"event: {dto.type.value}\ndata: {payload}\n\n".encode()
