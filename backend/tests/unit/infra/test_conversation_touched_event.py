"""`ConversationTouchedEvent`: Redis stream serialization and the SSE wire
mapping of the per-user event stream."""

import json
from datetime import datetime, timezone

import pytest

from src.api.v1.chat.sse import user_event_message
from src.infra.task_queue.chat_streams import (
    ConversationTouchedEvent,
    serialize_conversation_touched_event,
)

_UPDATED_AT = datetime(2026, 7, 1, 12, 30, tzinfo=timezone.utc)


def test_serialize_carries_event_type_and_iso_updated_at() -> None:
    fields = serialize_conversation_touched_event(
        ConversationTouchedEvent(conversation_id="c-1", updated_at=_UPDATED_AT.isoformat())
    )

    assert fields["event_type"] == "ConversationTouchedEvent"
    assert json.loads(fields["payload"]) == {
        "conversation_id": "c-1",
        "updated_at": "2026-07-01T12:30:00+00:00",
    }


def test_user_event_message_maps_to_conversation_touched_wire_type() -> None:
    fields = serialize_conversation_touched_event(
        ConversationTouchedEvent(conversation_id="c-1", updated_at=_UPDATED_AT.isoformat())
    )

    name, body = user_event_message("5-0", fields["event_type"], json.loads(fields["payload"]))

    assert name == "conversation_touched"
    assert body == {
        "type": "conversation_touched",
        "cursor": "5-0",
        "conversation_id": "c-1",
        "updated_at": "2026-07-01T12:30:00+00:00",
    }


def test_user_event_message_still_rejects_unknown_types() -> None:
    with pytest.raises(ValueError):
        user_event_message("1-0", "NopeEvent", {})
