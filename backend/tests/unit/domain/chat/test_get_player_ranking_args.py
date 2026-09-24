import pytest
from pydantic import ValidationError

from src.domain.chat.tools.get_player_ranking import (
    GetPlayerRankingArgs,
    build_get_player_ranking_handler,
)
from src.domain.player_analytics.competition_names import resolve_competition_id
from src.domain.player_analytics.model.player_ranking import RankBy, RankingScope, SeasonWindow


def test_resolve_competition_id_accepts_code_and_unique_name() -> None:
    assert resolve_competition_id("GB1") == "GB1"
    assert resolve_competition_id("premier league") == "GB1"
    assert resolve_competition_id("Champions League") == "CL"


def test_resolve_competition_id_rejects_unknown_or_ambiguous() -> None:
    assert resolve_competition_id("") is None
    assert resolve_competition_id("no-such-cup") is None
    # "Cup" matches many names.
    assert resolve_competition_id("Cup") is None


def test_world_cup_args_forbid_season_filters() -> None:
    with pytest.raises(ValidationError):
        GetPlayerRankingArgs(
            scope=RankingScope.WORLD_CUP,
            rank_by=RankBy.GOALS,
            season_window="latest",
            competition="all",
        )


def test_transfermarkt_args_require_window_and_competition() -> None:
    with pytest.raises(ValidationError):
        GetPlayerRankingArgs(scope=RankingScope.TRANSFERMARKT, rank_by=RankBy.GOALS)


def test_transfermarkt_rejects_goalkeeper_world_cup_criterion() -> None:
    with pytest.raises(ValidationError):
        GetPlayerRankingArgs(
            scope=RankingScope.TRANSFERMARKT,
            rank_by=RankBy.SAVES,
            season_window="latest",
            competition="all",
        )


def test_saves_cannot_combine_with_outfield_position() -> None:
    with pytest.raises(ValidationError):
        GetPlayerRankingArgs(
            scope=RankingScope.WORLD_CUP,
            rank_by=RankBy.SAVES,
            position="FWD",
        )


def test_min_floors_are_optional_on_args() -> None:
    args = GetPlayerRankingArgs(
        scope=RankingScope.TRANSFERMARKT,
        rank_by=RankBy.GOAL_CONTRIBUTIONS_PER90,
        season_window=SeasonWindow.LATEST,
        competition="all",
        min_appearances=10,
        min_goals=10,
        min_assists=10,
    )
    assert args.min_appearances == 10
    assert args.min_goals == 10
    assert args.min_assists == 10


@pytest.mark.asyncio
async def test_handler_returns_error_for_unknown_competition() -> None:
    class _Repo:
        async def get_player_ranking(self, request):
            raise AssertionError("must not query")

        async def get_player_analysis(self, player_query):
            raise AssertionError("unused")

        async def get_player_comparison(self, player_a_query, player_b_query):
            raise AssertionError("unused")

    handler = build_get_player_ranking_handler(_Repo())
    args = GetPlayerRankingArgs(
        scope=RankingScope.TRANSFERMARKT,
        rank_by=RankBy.GOALS,
        season_window=SeasonWindow.LATEST,
        competition="not-a-real-cup",
    )
    result = await handler(args)
    assert result.widget_data is None
    assert "No competition matching" in result.content
