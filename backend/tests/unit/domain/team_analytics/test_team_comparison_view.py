"""Pure assembly of a team comparison. No database."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.domain.chat.exceptions.chat_exceptions import TeamNotFoundError
from src.domain.chat.tools.get_team_comparison import (
    GetTeamComparisonArgs,
    build_get_team_comparison_handler,
)
from src.domain.chat.tools.registry import ALL_TOOL_SCHEMAS, build_tool_registry
from src.infra.postgres.repositories._team_comparison_facts import (
    DepthFact,
    FieldBenchmarks,
    GroupFact,
    MatchFact,
    PlayerFact,
    TeamProfile,
    TeamStatFact,
)
from src.infra.postgres.repositories._team_comparison_view import assemble_team_comparison


def _profile(team_id: int, name: str, code: str) -> TeamProfile:
    return TeamProfile(
        team_id=team_id,
        name=name,
        fifa_code=code,
        confederation="UEFA",
        group_letter="A",
        manager_name=f"{name} coach",
        fifa_ranking_pre_tournament=team_id,
        elo_rating=1800 + team_id,
        transfermarkt_average_age=31.2,
        transfermarkt_market_value_eur=400_000_000,
        transfermarkt_squad_size=23,
    )


def _match(**overrides) -> MatchFact:
    values = {
        "match_id": 1,
        "stage_name": "Group Stage",
        "is_knockout": False,
        "home_team_id": 1,
        "away_team_id": 2,
        "home_score": 0,
        "away_score": 0,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "home_xg": 1.0,
        "away_xg": 1.0,
    }
    values.update(overrides)
    return MatchFact(**values)


def _stat(team_id: int, possession: int, fouls: int) -> TeamStatFact:
    return TeamStatFact(
        team_id=team_id,
        possession_pct=possession,
        total_shots=10,
        shots_on_target=4,
        corners=5,
        fouls=fouls,
        offsides=1,
        saves=2,
    )


def _player(**overrides) -> PlayerFact:
    values = {
        "player_id": 10,
        "team_id": 1,
        "name": "Ada Forward",
        "position": "FW",
        "club": "Club A",
        "market_value_eur": 80_000_000,
        "caps": 40,
        "date_of_birth": date(1998, 3, 1),
        "height_cm": 180,
        "appearances": 1,
        "starts": 1,
        "minutes": 70,
        "goals": 1,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "penalty_goals": 0,
        "own_goals": 0,
        "clean_sheets": None,
        "saves": None,
        "goals_conceded": None,
    }
    values.update(overrides)
    return PlayerFact(**values)


def _field() -> FieldBenchmarks:
    return FieldBenchmarks(
        goals_per_game=0,
        xg_per_game=1,
        possession_pct=45,
        shots_per_game=10,
        shots_on_target_per_game=4,
        shot_accuracy_pct=40,
        conversion_pct=0,
        clean_sheets_per_game=1,
        corners_per_game=5,
        fouls_per_game=10,
        offsides_per_game=1,
        saves_per_game=2,
        yellow_per_match=0,
        group_points=1,
    )


def _comparison(**overrides):
    values = {
        "team_a": _profile(1, "North", "NOR"),
        "team_b": _profile(2, "South", "SOU"),
        "matches": [_match()],
        "opponents": {1: ("NOR", "North"), 2: ("SOU", "South")},
        "team_stats": [_stat(1, 60, 16), _stat(2, 45, 10)],
        "cards": {},
        "players": [],
        "depth": {},
        "groups": {
            1: GroupFact(played=1, points=1, goal_difference=0),
            2: GroupFact(played=1, points=1, goal_difference=0),
        },
        "field": _field(),
    }
    values.update(overrides)
    return assemble_team_comparison(**values)


def test_draw_records_a_meeting_and_names_possession_and_fouls() -> None:
    comparison = _comparison()

    assert comparison.team_a.record.drawn == 1
    assert comparison.team_a.record.goals_for == 0
    assert comparison.team_a.rates.possession_pct == 60
    assert comparison.team_a.rates.xg_difference == 0
    assert comparison.meetings[0].team_a_result == "D"
    assert comparison.meetings[0].penalty_score is None
    assert comparison.team_a.group.points == 1
    assert comparison.team_a.standing_label == "Group Stage · unbeaten so far"

    a_notes = [note for note in comparison.strengths_and_flaws if note.side == "a"]
    assert [note.kind for note in a_notes] == ["strength", "flaw"]
    assert a_notes[0].label == "Possession"
    assert a_notes[0].detail.startswith("60.0% vs 45.0%")
    assert a_notes[1].label == "Fouls per game"
    assert not any(note.side == "b" for note in comparison.strengths_and_flaws)


def test_penalty_shootout_is_a_loss_for_the_side_that_misses() -> None:
    comparison = _comparison(
        matches=[_match(home_score=1, away_score=1, home_penalty_score=3, away_penalty_score=4)],
        groups={
            1: GroupFact(played=1, points=0, goal_difference=0),
            2: GroupFact(played=1, points=3, goal_difference=0),
        },
    )

    assert comparison.team_a.record.lost == 1
    assert comparison.team_a.record.goals_for == 1
    assert comparison.meetings[0].team_a_result == "L"
    assert comparison.meetings[0].penalty_score == "3–4"
    assert comparison.team_a.standing_label == "Group Stage · out 1–1 to South"
    assert comparison.team_a.match_results[0].result == "L"


def test_squad_profile_uses_roster_age_and_value_not_transfermarkt() -> None:
    players = [
        _player(player_id=1, market_value_eur=100, date_of_birth=date(2005, 1, 1), minutes=20),
        _player(
            player_id=2,
            name="Bea Mid",
            position="MF",
            market_value_eur=50,
            date_of_birth=date(1990, 1, 1),
            minutes=90,
            goals=3,
            assists=2,
        ),
        _player(
            player_id=3,
            name="Cara Keeper",
            position="GK",
            market_value_eur=25,
            date_of_birth=date(1996, 6, 1),
            minutes=90,
            goals=0,
            saves=4,
            clean_sheets=1,
            goals_conceded=2,
        ),
        _player(
            player_id=4,
            team_id=2,
            name="Dora Striker",
            market_value_eur=40,
            date_of_birth=date(2003, 8, 1),
            minutes=10,
            goals=1,
        ),
    ]
    comparison = _comparison(
        players=players,
        depth={1: DepthFact(distinct_starters=2, starter_minutes=160, total_minutes=200)},
    )

    squad = comparison.team_a.squad
    assert squad.roster_size == 3
    assert squad.average_age == 29.0
    assert squad.total_market_value_eur == 175
    assert squad.youngest_age == 21
    assert squad.oldest_age == 36
    assert squad.under_23_pct == 33.3
    assert squad.over_30_pct == 33.3
    assert squad.top_three_value_share_pct == 100.0
    assert squad.distinct_starters == 2
    assert squad.starter_minutes_share_pct == 80.0
    assert squad.transfermarkt_average_age == 31.2
    assert squad.transfermarkt_market_value_eur == 400_000_000
    assert comparison.team_a.top_scorer is not None
    assert comparison.team_a.top_scorer.name == "Bea Mid"
    assert comparison.team_a.most_minutes is not None
    assert comparison.team_a.most_minutes.name == "Bea Mid"

    groups = {group.position: group for group in comparison.positions}
    assert [player.name for player in groups["MID"].team_a_players] == ["Bea Mid"]
    assert groups["GK"].team_a_players[0].saves == 4
    assert groups["GK"].team_a_players[0].saves_per90 == 4.0
    assert groups["GK"].team_a_players[0].goals_conceded_per90 == 2.0
    assert groups["FWD"].team_a_players[0].saves is None
    assert [player.name for player in groups["FWD"].team_a_players] == ["Ada Forward"]
    assert groups["FWD"].team_b_players[0].name == "Dora Striker"
    assert groups["DEF"].team_a_players == []
    assert groups["MID"].team_a_rollup.goals == 3
    assert comparison.team_a.squad.average_age != squad.transfermarkt_average_age


def test_empty_squad_leaves_age_unset() -> None:
    comparison = _comparison()
    assert comparison.team_a.squad.roster_size == 0
    assert comparison.team_a.squad.average_age is None
    assert comparison.team_a.top_scorer is None


def test_widget_payload_is_camel_case() -> None:
    payload = _comparison().model_dump(mode="json", by_alias=True)
    assert payload["teamA"]["code"] == "NOR"
    assert payload["teamA"]["rates"]["xgDifference"] == 0
    assert payload["strengthsAndFlaws"][0]["kind"] == "strength"
    assert payload["positions"][0]["position"] == "GK"
    assert "team_a" not in payload


def test_args_reject_an_unknown_field() -> None:
    with pytest.raises(ValidationError):
        GetTeamComparisonArgs(team_a_name="North", team_b_name="South", extra="no")


def test_schema_is_registered() -> None:
    names = [schema["function"]["name"] for schema in ALL_TOOL_SCHEMAS]
    assert "get_team_comparison" in names
    tool = build_tool_registry(object(), object(), object())["get_team_comparison"]
    assert tool.widget_type == "team_compare_widget"
    assert tool.args_model is GetTeamComparisonArgs


@pytest.mark.asyncio
async def test_handler_returns_an_error_without_a_widget_when_a_team_is_missing() -> None:
    class _Repo:
        async def get_team_comparison(self, team_a_query: str, team_b_query: str):
            raise TeamNotFoundError(f"No team found matching '{team_b_query}'.")

    handler = build_get_team_comparison_handler(_Repo())
    result = await handler(GetTeamComparisonArgs(team_a_name="North", team_b_name="Nowhere"))

    assert result.widget_data is None
    assert "Nowhere" in result.content


@pytest.mark.asyncio
async def test_handler_emits_camel_case_widget_data() -> None:
    comparison = _comparison()

    class _Repo:
        async def get_team_comparison(self, team_a_query: str, team_b_query: str):
            return comparison

    handler = build_get_team_comparison_handler(_Repo())
    result = await handler(GetTeamComparisonArgs(team_a_name="North", team_b_name="South"))

    assert result.widget_data is not None
    assert result.widget_data["teamA"]["name"] == "North"
    assert result.widget_data["teamB"]["name"] == "South"
