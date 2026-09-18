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
