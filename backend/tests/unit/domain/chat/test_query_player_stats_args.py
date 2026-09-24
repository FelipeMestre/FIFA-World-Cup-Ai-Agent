import pytest
from pydantic import ValidationError

from src.domain.chat.tools.query_player_stats import (
    QueryFilterArg,
    QueryPlayerStatsArgs,
    build_query_player_stats_handler,
)
from src.domain.player_analytics.competition_names import resolve_competition_id
from src.domain.player_analytics.model.player_ranking import (
    FilterOp,
    PlayerStatField,
    QueryDataset,
    SeasonWindow,
)


def test_resolve_competition_id_accepts_code_and_unique_name() -> None:
    assert resolve_competition_id("GB1") == "GB1"
    assert resolve_competition_id("premier league") == "GB1"
    assert resolve_competition_id("Champions League") == "CL"


def test_resolve_competition_id_rejects_unknown_or_ambiguous() -> None:
    assert resolve_competition_id("") is None
    assert resolve_competition_id("no-such-cup") is None
    assert resolve_competition_id("Cup") is None


def test_world_cup_args_forbid_season_filters() -> None:
    with pytest.raises(ValidationError):
        QueryPlayerStatsArgs(
            dataset=QueryDataset.WORLD_CUP,
            sort_by=PlayerStatField.GOALS,
            season_window="latest",
            competition="all",
        )


def test_club_seasons_args_require_window_and_competition() -> None:
    with pytest.raises(ValidationError):
        QueryPlayerStatsArgs(dataset=QueryDataset.CLUB_SEASONS, sort_by=PlayerStatField.GOALS)


def test_club_seasons_rejects_world_cup_only_field() -> None:
    with pytest.raises(ValidationError):
        QueryPlayerStatsArgs(
            dataset=QueryDataset.CLUB_SEASONS,
            sort_by=PlayerStatField.SAVES,
            season_window="latest",
            competition="all",
        )


def test_saves_cannot_combine_with_outfield_position() -> None:
    with pytest.raises(ValidationError):
        QueryPlayerStatsArgs(
            dataset=QueryDataset.WORLD_CUP,
            sort_by=PlayerStatField.SAVES,
            filters=[QueryFilterArg(field=PlayerStatField.POSITION, op=FilterOp.EQ, value="FWD")],
        )


def test_filters_accept_stat_floors() -> None:
    args = QueryPlayerStatsArgs(
        dataset=QueryDataset.CLUB_SEASONS,
        sort_by=PlayerStatField.GOAL_CONTRIBUTIONS_PER90,
        season_window=SeasonWindow.LATEST,
        competition="all",
        filters=[
            QueryFilterArg(field=PlayerStatField.APPEARANCES, op=FilterOp.GTE, value=10),
            QueryFilterArg(field=PlayerStatField.GOALS, op=FilterOp.GTE, value=10),
            QueryFilterArg(field=PlayerStatField.ASSISTS, op=FilterOp.GTE, value=10),
        ],
    )
    assert len(args.filters) == 3


def test_position_rejects_range_op() -> None:
    with pytest.raises(ValidationError):
        QueryPlayerStatsArgs(
            dataset=QueryDataset.WORLD_CUP,
            sort_by=PlayerStatField.GOALS,
            filters=[QueryFilterArg(field=PlayerStatField.POSITION, op=FilterOp.GTE, value="FWD")],
        )


@pytest.mark.asyncio
async def test_handler_returns_error_for_unknown_competition() -> None:
    class _Repo:
        async def query_player_stats(self, request):
            raise AssertionError("must not query")

        async def get_player_analysis(self, player_query):
            raise AssertionError("unused")

        async def get_player_comparison(self, player_a_query, player_b_query):
            raise AssertionError("unused")

    handler = build_query_player_stats_handler(_Repo())
    args = QueryPlayerStatsArgs(
        dataset=QueryDataset.CLUB_SEASONS,
        sort_by=PlayerStatField.GOALS,
        season_window=SeasonWindow.LATEST,
        competition="not-a-real-cup",
    )
    result = await handler(args)
    assert result.widget_data is None
    assert "No competition matching" in result.content
