from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class Match:
    id: int
    date: date
    kickoff_time_utc: time
    stage_id: int
    venue_id: int
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    home_penalty_score: int | None
    away_penalty_score: int | None
    status: str
    result_type: str
    home_xg: float
    away_xg: float
    referee_id: int
    player_of_the_match_id: int


@dataclass(frozen=True, slots=True)
class MatchSearchRow:
    """One `MatchRepositoryInterface.search()` result -- a `Match` plus the
    home/away team names the match-selector chip needs to render a label
    like "Brazil vs Argentina". Neither `Match` itself nor a bare query row
    carries team names (they live on `NationalTeamSchema`), so this is a
    search-only shape, not a general-purpose replacement for `Match`.
    """

    match: Match
    home_team_name: str
    away_team_name: str
