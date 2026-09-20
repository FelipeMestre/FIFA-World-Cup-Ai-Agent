"""Pure unit tests for `RosterScopingService` -- in-memory fixtures, no DB."""

from src.domain.ingestion.services.roster_scoping_service import RosterScopingService
from src.domain.national_teams.model.national_team import NationalTeam


def _team(team_id: int, name: str, fifa_code: str) -> NationalTeam:
    return NationalTeam(
        id=team_id,
        name=name,
        fifa_code=fifa_code,
        group_letter="A",
        confederation="UEFA",
        fifa_ranking_pre_tournament=1,
        elo_rating=2000,
        manager_name="Someone",
    )


def test_matches_by_normalized_country_name() -> None:
    teams = [_team(10, "Argentina", "ARG")]
    national_teams = [
        {"national_team_id": 99, "country_name": "Argentina"},
        {"national_team_id": 5, "country_name": "Brazil"},
    ]

    result = RosterScopingService().resolve_national_teams(teams, national_teams)

    assert result == {10: 99}


def test_falls_back_to_fifa_code_when_name_differs() -> None:
    teams = [_team(10, "Cote d'Ivoire", "CIV")]
    national_teams = [{"national_team_id": 77, "country_name": "CIV"}]

    result = RosterScopingService().resolve_national_teams(teams, national_teams)

    assert result == {10: 77}


def test_falls_back_to_known_name_alias() -> None:
    # FIFA's synthetic dataset calls it "IR Iran"; Transfermarkt calls it
    # plain "Iran" -- neither normalization nor the fifa_code fallback
    # catches this, so it's a known, explicit alias.
    teams = [_team(10, "IR Iran", "IRN")]
    national_teams = [{"national_team_id": 42, "country_name": "Iran"}]

    result = RosterScopingService().resolve_national_teams(teams, national_teams)

    assert result == {10: 42}


def test_unmatched_team_is_excluded() -> None:
    teams = [_team(10, "Nowhereland", "NWH")]
    national_teams = [{"national_team_id": 5, "country_name": "Brazil"}]

    result = RosterScopingService().resolve_national_teams(teams, national_teams)

    assert result == {}


def test_national_team_ids_returns_value_set() -> None:
    result = RosterScopingService().national_team_ids({10: 99, 20: 5, 30: 99})

    assert result == {99, 5}
