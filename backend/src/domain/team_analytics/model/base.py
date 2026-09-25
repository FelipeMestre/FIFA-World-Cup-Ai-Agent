"""Shared camelCase read-model pieces used by team analysis and comparison."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

ResultLetter = Literal["W", "D", "L"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TeamRecord(CamelModel):
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int


class TeamMatchResult(CamelModel):
    stage: str
    opponent_code: str
    opponent_name: str
    score: str
    result: ResultLetter
