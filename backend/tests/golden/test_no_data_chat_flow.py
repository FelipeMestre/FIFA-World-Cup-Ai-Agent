"""No-data cases at the tool-loop and chat-service level, driven by a scripted model.

What the model reads when a tool finds nothing, whether any widget leaks into the turn, and
the first message of a conversation with no history and an empty cache. The unit suite
(`tests/unit/domain/chat/test_chat_service_history_rebuild.py`) already pins the empty-cache
rebuild with fakes for every collaborator; here the registry and repositories are real.

The chat-service test never creates a conversation row (writes stay inside the fixture ID
ranges), so the assistant-persistence step fails soft on its foreign key; that incidental
`PersistenceFailedEvent` is not asserted.
"""

import json
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.services.chat_service import SYSTEM_PROMPT, ChatService
from src.domain.chat.services.chat_turn_events import MessageDoneEvent
from src.domain.chat.services.tool_call_executor import ToolWidgetResult, WidgetReadyEvent
from src.domain.chat.tools.registry import ToolDefinition
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.postgres.repositories.match_repository import get_match_repository
from src.infra.postgres.repositories.national_team_repository import get_national_team_repository
from tests.golden.no_data_cases import (
    NO_PLAYERS_MATCHED_ERROR,
    UNKNOWN_PLAYER,
    UNKNOWN_PLAYER_ERROR,
    UNKNOWN_TEAM,
    UNKNOWN_TEAM_ERROR,
)
from tests.golden.tools import (
    InMemoryConversationCache,
    ScriptedOpenRouterClient,
    final_answer_response,
    resolved_turn,
    run_turn,
    tool_call_response,
)

_ANSWER = "I could not find data for that."
_QUESTION = "How did they do?"
_USER_ID = 1

_NO_DATA_CALLS = [
    ("get_team_analysis", {"team_name": UNKNOWN_TEAM}, UNKNOWN_TEAM_ERROR),
    (
        "get_team_comparison",
        {"team_a_name": "Valdoria", "team_b_name": UNKNOWN_TEAM},
        UNKNOWN_TEAM_ERROR,
    ),
    ("get_player_analysis", {"player_name": UNKNOWN_PLAYER}, UNKNOWN_PLAYER_ERROR),
    (
        "get_player_comparison",
        {"player_a_name": "Rafael Ortegon", "player_b_name": UNKNOWN_PLAYER},
        UNKNOWN_PLAYER_ERROR,
    ),
    (
        "get_match_analysis",
        {"home_team_name": "Valdoria", "away_team_name": UNKNOWN_TEAM},
        f"No match found between 'Valdoria' and '{UNKNOWN_TEAM}'.",
    ),
    (
        "query_player_stats",
        {
            "dataset": "world_cup",
            "sort_by": "goals",
            "filters": [{"field": "goals", "op": "gte", "value": 99}],
        },
        NO_PLAYERS_MATCHED_ERROR,
    ),
]


@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected_error"),
    _NO_DATA_CALLS,
    ids=[call[0] for call in _NO_DATA_CALLS],
)
async def test_no_data_result_is_handed_to_the_model_as_an_error_and_emits_no_widget(
    registry: dict[str, ToolDefinition], tool_name: str, arguments: dict, expected_error: str
) -> None:
    client = ScriptedOpenRouterClient(
        [tool_call_response("call-1", tool_name, arguments), final_answer_response(_ANSWER)]
    )

    events = await run_turn(registry, client, _QUESTION)

    second_call = client.calls[1]
    assert second_call[-2]["role"] == "assistant"
    assert second_call[-2]["tool_calls"][0]["function"]["name"] == tool_name
    tool_message = second_call[-1]
    assert (tool_message["role"], tool_message["name"]) == ("tool", tool_name)
    assert json.loads(tool_message["content"]) == {"error": expected_error}
    assert not any(isinstance(event, WidgetReadyEvent) for event in events)
    assert resolved_turn(events).content_segments == [_ANSWER]


async def test_team_that_exists_but_never_played_still_emits_a_widget_of_zeros(
    registry: dict[str, ToolDefinition],
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", "get_team_analysis", {"team_name": "Ostravia"}),
            final_answer_response(_ANSWER),
        ]
    )

    events = await run_turn(registry, client, _QUESTION)

    widgets = [event.widget for event in events if isinstance(event, WidgetReadyEvent)]
    assert [(widget.tool_name, widget.widget_type) for widget in widgets] == [
        ("get_team_analysis", "team_widget")
    ]
    assert widgets[0].data["record"] == {
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goalsFor": 0,
        "goalsAgainst": 0,
    }
    assert isinstance(resolved_turn(events).content_segments[0], ToolWidgetResult)


async def test_overlong_name_is_rejected_to_the_model_without_running_the_handler(
    registry: dict[str, ToolDefinition],
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", "get_team_analysis", {"team_name": "x" * 129}),
            final_answer_response(_ANSWER),
        ]
    )

    events = await run_turn(registry, client, _QUESTION)

    tool_content = client.calls[1][-1]["content"]
    assert tool_content.startswith("Invalid arguments for 'get_team_analysis'")
    assert "at most 128 characters" in tool_content
    assert not any(isinstance(event, WidgetReadyEvent) for event in events)


async def test_malformed_match_date_escapes_the_tool_loop_instead_of_reaching_the_model(
    registry: dict[str, ToolDefinition],
) -> None:
    """Today's behavior, reported as a finding: nothing in the executor or the handler turns
    the `ValueError` from `date.fromisoformat` into a tool message, so the whole turn dies."""
    client = ScriptedOpenRouterClient(
        [
            tool_call_response(
                "call-1",
                "get_match_analysis",
                {"home_team_name": "Valdoria", "away_team_name": "Karsovia", "date": "June 14"},
            ),
            final_answer_response(_ANSWER),
        ]
    )

    with pytest.raises(ValueError):
        await run_turn(registry, client, _QUESTION)

    assert len(client.calls) == 1


@pytest.fixture
def chat_service_factory(golden_session: AsyncSession, registry: dict[str, ToolDefinition]):
    def _build(client: ScriptedOpenRouterClient, cache: InMemoryConversationCache) -> ChatService:
        return ChatService(
            conversation_cache=cache,
            openrouter_client=client,
            tool_registry=registry,
            conversation_repo=get_conversation_repository(golden_session),
            chat_message_repo=get_chat_message_repository(golden_session),
            match_repo=get_match_repository(golden_session),
            national_team_repo=get_national_team_repository(golden_session),
            session=golden_session,
        )

    return _build


async def test_first_message_with_empty_history_and_cache_sends_only_prompt_and_question(
    chat_service_factory,
) -> None:
    client = ScriptedOpenRouterClient([final_answer_response(_ANSWER)])
    service = chat_service_factory(client, InMemoryConversationCache())

    events = [event async for event in service.send_message(uuid4(), _USER_ID, _QUESTION)]

    assert client.calls[0] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _QUESTION},
    ]
    done = events[-1]
    assert isinstance(done, MessageDoneEvent)
    assert done.content == _ANSWER


async def test_not_found_tool_result_leaves_the_turn_without_widgets_or_cached_tool_messages(
    chat_service_factory,
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", "get_team_analysis", {"team_name": UNKNOWN_TEAM}),
            final_answer_response(_ANSWER),
        ]
    )
    cache = InMemoryConversationCache()
    service = chat_service_factory(client, cache)

    events = [event async for event in service.send_message(uuid4(), _USER_ID, _QUESTION)]

    assert json.loads(client.calls[1][-1]["content"]) == {"error": UNKNOWN_TEAM_ERROR}
    assert not any(isinstance(event, WidgetReadyEvent) for event in events)
    done = events[-1]
    assert isinstance(done, MessageDoneEvent)
    assert done.content_segments == [_ANSWER]
    assert [[(m.role, m.content) for m in saved] for saved in cache.saved] == [
        [("user", _QUESTION), ("assistant", _ANSWER)]
    ]
