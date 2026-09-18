from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Team:
    id: int
    name: str
    fifa_code: str
    group_letter: str
    confederation: str
    fifa_ranking_pre_tournament: int
    elo_rating: int
    manager_name: str
