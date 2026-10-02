"""Golden cases for the tool loop around the real registry: the executor validates model
arguments, caps runaway loops, and tags widgets, driven by a scripted model (no LLM).
"""

import json

import pytest

from src.domain.chat.services.tool_call_executor import (
    CLARIFICATION_REQUEST,
    MAX_ITERATIONS,
    ToolCallRequestedEvent,
    WidgetReadyEvent,
)
from src.domain.chat.tools.registry import ToolDefinition
from src.infra.openrouter.schemas import ChatCompletionResult, ToolLoopCapReached
from tests.golden import fixture_data
from tests.golden.tools import (
    ScriptedOpenRouterClient,
    call_tool,
    final_answer_response,
    resolved_turn,
    run_turn,
    tool_call_response,
)

_VALID_CALLS = {
    "get_team_analysis": {"team_name": "Valdoria"},
    "get_player_analysis": {"player_name": "Rafael Ortegon"},
    "get_match_analysis": {"home_team_name": "Valdoria", "away_team_name": "Sérvenia"},
    "get_player_comparison": {
        "player_a_name": "Rafael Ortegon",
        "player_b_name": "Dario Montefusco",
    },
    "query_player_stats": {
        "dataset": "world_cup",
        "sort_by": "goals",
        "filters": [{"field": "nationality", "op": "eq", "value": "VLD"}],
    },
    "get_team_comparison": {"team_a_name": "Valdoria", "team_b_name": "Karsovia"},
}
_WIDGET_TYPES = {
    "get_team_analysis": "team_widget",
    "get_player_analysis": "player_widget",
    "get_match_analysis": "match_widget",
    "get_player_comparison": "compare_widget",
    "query_player_stats": "ranking_widget",
    "get_team_comparison": "team_compare_widget",
}


@pytest.mark.parametrize("tool_name", sorted(_WIDGET_TYPES))
async def test_each_widget_tool_declares_its_widget_type_and_returns_widget_data(
    registry: dict[str, ToolDefinition], tool_name: str
) -> None:
    outcome = await call_tool(registry, tool_name, **_VALID_CALLS[tool_name])

    assert registry[tool_name].widget_type == _WIDGET_TYPES[tool_name]
    assert outcome.widget_data is not None
    assert "error" not in outcome.payload


def test_tool_without_a_widget_declares_no_widget_type(
    registry: dict[str, ToolDefinition],
) -> None:
    assert registry["get_current_utc_time"].widget_type is None


async def test_widget_data_is_camel_case_while_model_content_is_snake_case(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, "get_team_analysis", team_name="Valdoria")

    assert "goal_difference" in outcome.payload
    assert outcome.widget_data is not None
    assert "goalDifference" in outcome.widget_data
    assert "goal_difference" not in outcome.widget_data


async def test_executor_tags_the_widget_with_tool_name_type_and_data_then_answers(
    registry: dict[str, ToolDefinition],
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", "get_team_analysis", {"team_name": "Valdoria"}),
            final_answer_response("Valdoria won two of three."),
        ]
    )

    events = await run_turn(registry, client, "How did Valdoria do?")

    widget_events = [event for event in events if isinstance(event, WidgetReadyEvent)]
    assert len(widget_events) == 1
    widget = widget_events[0].widget
    assert (widget.tool_call_id, widget.tool_name, widget.widget_type) == (
        "call-1",
        "get_team_analysis",
        "team_widget",
    )
    assert widget.data["id"] == str(fixture_data.VALDORIA.team_id)
    terminal = resolved_turn(events)
    assert isinstance(terminal.result, ChatCompletionResult)
    assert terminal.result.content == "Valdoria won two of three."
    tool_message = client.calls[1][-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"])["record"]["won"] == 2


async def test_a_tool_error_result_reaches_the_model_and_produces_no_widget(
    registry: dict[str, ToolDefinition],
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", "get_team_analysis", {"team_name": "Nowhereland"}),
            final_answer_response("I could not find that team."),
        ]
    )

    events = await run_turn(registry, client, "How did Nowhereland do?")

    assert not any(isinstance(event, WidgetReadyEvent) for event in events)
    tool_message = client.calls[1][-1]
    assert json.loads(tool_message["content"]) == {"error": "No team found matching 'Nowhereland'."}


@pytest.mark.parametrize(
    ("tool_name", "arguments", "message_part"),
    [
        ("get_team_analysis", {}, "Invalid arguments for 'get_team_analysis'"),
        ("get_team_analysis", {"team_name": "Valdoria", "year": 2026}, "year"),
        ("get_team_analysis", {"team_name": ""}, "team_name"),
        ("get_player_comparison", {"player_a_name": "Rafael Ortegon"}, "player_b_name"),
        ("query_player_stats", {"dataset": "world_cup", "sort_by": "shots"}, "sort_by"),
        (
            "query_player_stats",
            {"dataset": "club_seasons", "sort_by": "goals"},
            "seasons and competition are required",
        ),
        ("get_team_analysis", "{not json", "Invalid arguments for 'get_team_analysis'"),
    ],
    ids=[
        "missing-required",
        "extra-field",
        "empty-string",
        "missing-second-player",
        "non-allowlisted-sort-field",
        "club-seasons-without-seasons",
        "malformed-json",
    ],
)
async def test_invalid_tool_arguments_are_rejected_to_the_model_without_running_the_handler(
    registry: dict[str, ToolDefinition], tool_name: str, arguments: dict | str, message_part: str
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", tool_name, arguments),
            final_answer_response("Sorry, I could not run that."),
        ]
    )

    events = await run_turn(registry, client, "anything")

    tool_message = client.calls[1][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["content"].startswith("Invalid arguments")
    assert message_part in tool_message["content"]
    assert not any(isinstance(event, WidgetReadyEvent) for event in events)
    assert isinstance(resolved_turn(events).result, ChatCompletionResult)


async def test_unknown_tool_name_is_rejected_to_the_model(
    registry: dict[str, ToolDefinition],
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response("call-1", "get_player_salary", {"player_name": "Rafael Ortegon"}),
            final_answer_response("I have no such tool."),
        ]
    )

    await run_turn(registry, client, "What does Ortegon earn?")

    assert client.calls[1][-1]["content"] == "Unknown tool 'get_player_salary'."


async def test_runaway_tool_loop_stops_at_the_iteration_cap_with_a_clarification_request(
    registry: dict[str, ToolDefinition],
) -> None:
    responses = [
        tool_call_response(
            f"call-{index}",
            "get_team_analysis",
            {"team_name": "Valdoria"},
            content=f"Checking attempt {index}. ",
        )
        for index in range(MAX_ITERATIONS)
    ]
    client = ScriptedOpenRouterClient(responses)

    events = await run_turn(registry, client, "Loop forever")

    result = resolved_turn(events).result
    assert isinstance(result, ToolLoopCapReached)
    assert result.clarification == CLARIFICATION_REQUEST
    assert "Checking attempt 0." in result.partial_content
    assert f"Checking attempt {MAX_ITERATIONS - 1}." in result.partial_content
    assert len(client.calls) == MAX_ITERATIONS
    requested = [event.name for event in events if isinstance(event, ToolCallRequestedEvent)]
    assert requested == ["get_team_analysis"] * MAX_ITERATIONS
    widgets = [event for event in events if isinstance(event, WidgetReadyEvent)]
    assert len(widgets) == MAX_ITERATIONS
    assert all(widget.widget.widget_type == "team_widget" for widget in widgets)


async def test_model_can_resolve_an_ambiguous_match_by_calling_again_with_the_stage(
    registry: dict[str, ToolDefinition],
) -> None:
    client = ScriptedOpenRouterClient(
        [
            tool_call_response(
                "call-1",
                "get_match_analysis",
                {"home_team_name": "Valdoria", "away_team_name": "Karsovia"},
            ),
            tool_call_response(
                "call-2",
                "get_match_analysis",
                {"home_team_name": "Valdoria", "away_team_name": "Karsovia", "stage": "Final"},
            ),
            final_answer_response("The final finished 1-1, Karsovia won on penalties."),
        ]
    )

    events = await run_turn(registry, client, "Valdoria vs Karsovia?")

    first_result = json.loads(client.calls[1][-1]["content"])
    assert len(first_result["candidates"]) == 2
    widgets = [event.widget for event in events if isinstance(event, WidgetReadyEvent)]
    assert [widget.data["id"] for widget in widgets] == ["995002"]
