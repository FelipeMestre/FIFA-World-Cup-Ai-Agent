"""Lookups from the fixture seeds for Layer B checks, so no number is typed a second time."""

from tests.golden import fixture_career, fixture_data, fixture_matches
from tests.golden.fixture_data import PlayerSeed, StatSeed, TeamSeed
from tests.golden.fixture_matches import MatchSeed


def player(player_id: int) -> PlayerSeed:
    return next(seed for seed in fixture_data.PLAYERS if seed.player_id == player_id)


def stat(player_id: int) -> StatSeed:
    return next(seed for seed in fixture_data.STATS if seed.player_id == player_id)


def match(match_id: int) -> MatchSeed:
    return next(seed for seed in fixture_matches.MATCHES if seed.match_id == match_id)


def team_by_code(code: str) -> TeamSeed:
    return next(seed for seed in fixture_data.TEAMS if seed.fifa_code == code)


def team_aliases(team: TeamSeed) -> set[str]:
    """Tokens a model may legitimately pass as the team argument."""
    return {team.team_name, team.fifa_code}


def season_row(real_player_id: int, season: str, competition_id: str) -> fixture_career.SeasonSeed:
    return next(
        seed
        for seed in fixture_career.SEASONS
        if (seed.real_player_id, seed.season, seed.competition_id)
        == (real_player_id, season, competition_id)
    )
