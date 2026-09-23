"""Redis-stream-entry -> SSE wire DTO serialization for the watch/reattach
endpoint (`conversation_router.py`). `redis_entry_to_dto` converts one
`chat:turn-stream:{conversation_id}` entry -- the flattened JSON shape
`infra/task_queue/chat_tasks.py`'s `serialize_chat_turn_event` writes -- into
the same `ChatStreamEvent` DTO shape `POST /chat/messages` used to stream
live, before generation moved to a background job (`generate_chat_reply_task`
now owns all `ChatTurnEvent` -> Redis-stream serialization directly).
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
