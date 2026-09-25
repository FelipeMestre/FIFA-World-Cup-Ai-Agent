"""Plain rows the team-comparison view assembles from. The query module maps
ORM results into these so the view can be tested without a database.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TeamProfile:
    team_id: int
    name: str
    fifa_code: str | None
    confederation: str
    group_letter: str | None
    manager_name: str | None
    fifa_ranking_pre_tournament: int | None
    elo_rating: int | None
    transfermarkt_average_age: float | None
    transfermarkt_market_value_eur: int | None
    transfermarkt_squad_size: int | None


@dataclass(frozen=True)
class MatchFact:
    match_id: int
    stage_name: str
    is_knockout: bool
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    home_penalty_score: int | None
    away_penalty_score: int | None
    home_xg: float
    away_xg: float


@dataclass(frozen=True)
class TeamStatFact:
    team_id: int
    possession_pct: int
    total_shots: int
    shots_on_target: int
    corners: int
    fouls: int
    offsides: int
    saves: int


@dataclass(frozen=True)
class PlayerFact:
    player_id: int
    team_id: int
    name: str
    position: str
    club: str
    market_value_eur: int
    caps: int
    date_of_birth: date
    height_cm: int
    appearances: int
    starts: int
    minutes: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int
    penalty_goals: int
    own_goals: int
    clean_sheets: int | None
    saves: int | None
    goals_conceded: int | None


@dataclass(frozen=True)
class DepthFact:
    distinct_starters: int
    starter_minutes: int
    total_minutes: int


@dataclass(frozen=True)
class GroupFact:
    played: int
    points: int
    goal_difference: int


@dataclass(frozen=True)
class FieldBenchmarks:
    goals_per_game: float
    xg_per_game: float
    possession_pct: float
    shots_per_game: float
    shots_on_target_per_game: float
    shot_accuracy_pct: float
    conversion_pct: float
    clean_sheets_per_game: float
    corners_per_game: float
    fouls_per_game: float
    offsides_per_game: float
    saves_per_game: float
    yellow_per_match: float
    group_points: float
