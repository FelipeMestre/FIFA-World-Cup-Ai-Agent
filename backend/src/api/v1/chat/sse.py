"""Redis-stream-entry -> SSE-frame message. Stream entries are parsed back
into a `ChatTurnEvent` by `parse_chat_turn_event` (the same mapping
`chat_turn_event_payload` writes); this module converts that domain event
into the JSON object the merged `GET /conversations/{id}/events` SSE
endpoint (`conversation_router.py`) sends for each frame.
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
from src.domain.chat.services.chat_turn_events import (
    CapReachedEvent,
    ChatTurnEvent,
    MessageDoneEvent,
    PersistenceFailedEvent,
    parse_chat_turn_event,
)
from src.domain.chat.services.tool_call_executor import (
    ContentDeltaEvent,
    ReasoningDeltaEvent,
    ToolCallRequestedEvent,
    ToolWidgetResult,
    WidgetReadyEvent,
)


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


def client_message(entry_id: str, event_type: str, payload: dict) -> dict:
    """One `turn` SSE frame's `data:` body. `cursor` is the Redis stream id."""
    if event_type == "UserMessageEvent":
        return {"type": "user_message", "cursor": entry_id, **payload}
    dto = redis_entry_to_dto(event_type, payload)
    body = dto.model_dump()
    body["cursor"] = entry_id
    return body


# Maps a per-user-stream `event_type` (the Redis stream field written by
# `serialize_conversation_created_event`/`serialize_conversation_categorized_event`)
# to the wire vocabulary `GET /users/events` (`user_events_router.py`) uses --
# both the frame's `event:` name and its `data.type` field share this same
# value, so one mapping derives both instead of hardcoding either.
_USER_EVENT_WIRE_TYPE: dict[str, str] = {
    "ConversationCreatedEvent": "conversation_created",
    "ConversationCategorizedEvent": "conversation_updated",
}


def user_event_message(entry_id: str, event_type: str, payload: dict) -> tuple[str, dict]:
    """One per-user-stream SSE frame, read from the per-user stream
    (`user_events_key`). Returns `(sse_event_name, data_body)`: the `event:`
    frame name to send, and the `data:` body -- `{"type": ..., "cursor": ...,
    **payload}`, the same shape `client_message` already uses for
    `UserMessageEvent`, for consistency between event kinds. Raises
    `ValueError` for an `event_type` this module doesn't know how to frame --
    fail fast rather than silently emit a malformed or type-less frame.
    """
    wire_type = _USER_EVENT_WIRE_TYPE.get(event_type)
    if wire_type is None:
        raise ValueError(f"Unhandled user-stream event_type: {event_type!r}")
    return wire_type, {"type": wire_type, "cursor": entry_id, **payload}
