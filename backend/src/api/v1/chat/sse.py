"""Redis-stream-entry -> SSE wire DTO serialization for the watch/reattach
endpoint (`conversation_router.py`). Stream entries are parsed back into a
`ChatTurnEvent` by `parse_chat_turn_event` (the same mapping
`chat_turn_event_payload` writes); this module only converts that domain
event into the SSE DTO.
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
    parse_chat_turn_event,
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


def _widget_part(widget: ToolWidgetResult) -> MessagePart:
    part_class = WIDGET_TYPE_TO_PART_CLASS.get(widget.widget_type)
    if part_class is None:
        raise ValueError(f"No MessagePart mapped for widget_type={widget.widget_type!r}")
    return part_class(data=widget.data)


def _segment_to_part(segment: str | ToolWidgetResult) -> MessagePart:
    if isinstance(segment, str):
        return TextPart(content=segment)
    return _widget_part(segment)


def to_dto(event: ChatTurnEvent) -> ChatStreamEvent:
    if isinstance(event, ReasoningDeltaEvent):
        return ReasoningDeltaEventDto(content=event.content)
    if isinstance(event, ContentDeltaEvent):
        return ContentDeltaEventDto(content=event.content)
    if isinstance(event, ToolCallRequestedEvent):
        return ToolCallEventDto(name=event.name)
    if isinstance(event, WidgetReadyEvent):
        return WidgetReadyEventDto(part=_widget_part(event.widget))
    if isinstance(event, CapReachedEvent):
        return CapReachedEventDto(content=event.content, clarification=event.clarification)
    if isinstance(event, PersistenceFailedEvent):
        return ErrorEventDto(detail=event.detail)
    if isinstance(event, MessageDoneEvent):
        parts = [_segment_to_part(segment) for segment in event.content_segments] or [
            TextPart(content=event.content)
        ]
        return MessageDoneEventDto(
            conversation_id=event.conversation_id, parts=parts, model=event.model
        )
    raise ValueError(f"Unhandled chat stream event: {event!r}")


def redis_entry_to_dto(event_type: str, payload: dict) -> ChatStreamEvent:
    event = parse_chat_turn_event(event_type, payload)
    if event is None:
        # The job's own failure marker (an exception class name, e.g.
        # "ChatServiceUnavailable") -- not a domain ChatTurnEvent.
        return ErrorEventDto(detail=payload.get("detail", event_type))
    return to_dto(event)


def format_sse(dto: ChatStreamEvent, event_id: str) -> bytes:
    """One SSE frame. `event_id` is the Redis stream id, so a client can
    resume with `after` / `Last-Event-ID` and receive only later entries.
    """
    payload = dto.model_dump_json(exclude={"type"})
    return f"id: {event_id}\nevent: {dto.type.value}\ndata: {payload}\n\n".encode()
