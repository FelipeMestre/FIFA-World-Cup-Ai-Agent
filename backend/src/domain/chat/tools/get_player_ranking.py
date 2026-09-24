"""`get_player_ranking` -- leaderboard counterpart to `get_player_analysis`.

The model must not call this tool until the user has picked a ranking
criterion. For Transfermarkt/club ranking it must also have season window
and competition. Missing choices are asked in assistant text (prompt-only,
no picker widget). World Cup numbers and club season numbers are never
mixed into one score.
"""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.chat.exceptions.chat_exceptions import RankingQueryError
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.domain.player_analytics.competition_names import (
    competition_name,
    resolve_competition_id,
)
from src.domain.player_analytics.model.player_ranking import (
    GK_ONLY_RANK_BY,
    WORLD_CUP_ONLY_RANK_BY,
    PlayerRankingRequest,
    RankBy,
    RankingScope,
    SeasonWindow,
)
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)

_RANK_BY_VALUES = [item.value for item in RankBy]

GET_PLAYER_RANKING_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_player_ranking",
        "description": (
            "Rank FIFA World Cup 2026 squad players by one statistic, with optional "
            "filters. There are two scopes that must never be mixed: world_cup uses "
            "tournament player_stat only; transfermarkt sums club season stats for "
            "players with an approved identity link (unlinked players are omitted, "
            "not ranked as zero). "
            "Do not call this tool until the user has chosen a ranking criterion "
            "(rank_by). For transfermarkt, also wait until they have chosen "
            "season_window (latest or last_three) and competition (all, or a named "
            "competition such as Premier League or Champions League). "
            "If any of those required choices are missing, reply in chat text with "
            "this options sheet and do not call the tool: "
            "(1) Ask how they want players ranked. "
            "(2) List optional filters: position (GK, DEF, MID, FWD); age range; "
            "height range; nationality (World Cup team); minimum appearances, "
            "minutes, goals, and assists in the ranking window. "
            "(3) For club/Transfermarkt ranking, list season: latest season or last "
            "three seasons; and competition: all competitions or a named one. "
            "(4) List World Cup criteria — outfield: goals, assists, G+A (totals or "
            "per 90), penalty goals, minutes, appearances, starts, yellow cards, "
            "red cards, fewest yellow cards, fewest red cards. GK only: saves, "
            "saves per 90, clean sheets, goals conceded, goals conceded per 90. "
            "(5) List club (Transfermarkt) criteria: goals, assists, G+A (totals or "
            "per 90), appearances, minutes, yellow cards, red cards, fewest yellow "
            "or red. No saves or conceded on the club scope. "
            "Do not offer shots, shots on target, average rating, or a blended "
            "World Cup + club score. After they answer, call this tool with "
            "structured arguments. If they later add a sample-size or output "
            "floor (e.g. more than 10 matches, 10+ goals, 10+ assists), pass "
            "min_appearances / min_goals / min_assists / min_minutes — those "
            "are applied in SQL. Do not claim a floor was applied unless you "
            "passed it. Inclusive: min_appearances=10 keeps players with 10 "
            "or more appearances in the ranking window."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["world_cup", "transfermarkt"],
                    "description": (
                        "world_cup = tournament stats. transfermarkt = summed club "
                        "season stats for approved identity links only."
                    ),
                },
                "rank_by": {
                    "type": "string",
                    "enum": _RANK_BY_VALUES,
                    "description": "Statistic to sort by. Must be valid for scope and position.",
                },
                "position": {
                    "type": "string",
                    "enum": ["GK", "DEF", "MID", "FWD"],
                    "description": "Optional position filter.",
                },
                "age_min": {
                    "type": "integer",
                    "description": "Minimum age as of 1 June 2026.",
                },
                "age_max": {
                    "type": "integer",
                    "description": "Maximum age as of 1 June 2026.",
                },
                "height_min_cm": {
                    "type": "integer",
                    "description": "Minimum height in centimetres (roster).",
                },
                "height_max_cm": {
                    "type": "integer",
                    "description": "Maximum height in centimetres (roster).",
                },
                "nationality": {
                    "type": "string",
                    "description": (
                        "World Cup national team name or FIFA code, e.g. Argentina or ARG."
                    ),
                },
                "season_window": {
                    "type": "string",
                    "enum": ["latest", "last_three"],
                    "description": "Required for transfermarkt. Forbidden for world_cup.",
                },
                "competition": {
                    "type": "string",
                    "description": (
                        "Required for transfermarkt: 'all' or a competition name/code "
                        "(Premier League, GB1, Champions League, CL, …)."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "How many players to return (1-25, default 10).",
                },
                "min_appearances": {
                    "type": "integer",
                    "description": (
                        "Keep players with at least this many appearances in the "
                        "ranking window (World Cup matches, or summed club apps)."
                    ),
                },
                "min_minutes": {
                    "type": "integer",
                    "description": (
                        "Keep players with at least this many minutes in the ranking window."
                    ),
                },
                "min_goals": {
                    "type": "integer",
                    "description": (
                        "Keep players with at least this many goals in the ranking window."
                    ),
                },
                "min_assists": {
                    "type": "integer",
                    "description": (
                        "Keep players with at least this many assists in the ranking window."
                    ),
                },
            },
            "required": ["scope", "rank_by"],
            "additionalProperties": False,
        },
    },
}


class GetPlayerRankingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: RankingScope
    rank_by: RankBy
    position: Literal["GK", "DEF", "MID", "FWD"] | None = None
    age_min: int | None = Field(default=None, ge=15, le=50)
    age_max: int | None = Field(default=None, ge=15, le=50)
    height_min_cm: int | None = Field(default=None, ge=140, le=230)
    height_max_cm: int | None = Field(default=None, ge=140, le=230)
    nationality: str | None = Field(default=None, min_length=1, max_length=128)
    season_window: SeasonWindow | None = None
    competition: str | None = Field(default=None, min_length=1, max_length=128)
    limit: int = Field(default=10, ge=1, le=25)
    min_appearances: int | None = Field(default=None, ge=0, le=200)
    min_minutes: int | None = Field(default=None, ge=0, le=20000)
    min_goals: int | None = Field(default=None, ge=0, le=200)
    min_assists: int | None = Field(default=None, ge=0, le=200)

    @model_validator(mode="after")
    def validate_scope_and_criterion(self) -> "GetPlayerRankingArgs":
        if self.position is not None and self.position != "GK" and self.rank_by in GK_ONLY_RANK_BY:
            raise ValueError(
                f"'{self.rank_by}' is a goalkeeper-only ranking; set position to GK "
                "or omit position."
            )
        if self.scope == RankingScope.TRANSFERMARKT:
            if self.season_window is None or self.competition is None:
                raise ValueError(
                    "season_window and competition are required for transfermarkt ranking."
                )
            if self.rank_by in WORLD_CUP_ONLY_RANK_BY:
                raise ValueError(
                    f"'{self.rank_by}' is not available on Transfermarkt season stats. "
                    "Use world_cup scope or a club criterion (goals, assists, G+A, "
                    "minutes, appearances, cards)."
                )
            return self
        if self.season_window is not None or self.competition is not None:
            raise ValueError("season_window and competition apply only to transfermarkt ranking.")
        return self


def _to_request(args: GetPlayerRankingArgs) -> PlayerRankingRequest:
    competition_id: str | None = None
    competition_label = "all competitions"
    if args.scope == RankingScope.TRANSFERMARKT:
        assert args.competition is not None
        if args.competition.strip().casefold() != "all":
            competition_id = resolve_competition_id(args.competition)
            if competition_id is None:
                raise RankingQueryError(
                    f"No competition matching '{args.competition}'. "
                    "Use 'all' or a known name such as Premier League or Champions League."
                )
            competition_label = competition_name(competition_id)
    return PlayerRankingRequest(
        scope=args.scope,
        rank_by=args.rank_by,
        position=args.position,
        age_min=args.age_min,
        age_max=args.age_max,
        height_min_cm=args.height_min_cm,
        height_max_cm=args.height_max_cm,
        nationality=args.nationality,
        season_window=args.season_window,
        competition_id=competition_id,
        competition_label=competition_label,
        limit=args.limit,
        min_appearances=args.min_appearances,
        min_minutes=args.min_minutes,
        min_goals=args.min_goals,
        min_assists=args.min_assists,
    )


def build_get_player_ranking_handler(repository: PlayerAnalyticsRepositoryInterface):
    async def get_player_ranking_handler(args: GetPlayerRankingArgs) -> ToolExecutionResult:
        try:
            request = _to_request(args)
            ranking = await repository.get_player_ranking(request)
        except RankingQueryError as exc:
            return ToolExecutionResult(content=json.dumps({"error": str(exc)}))
        if not ranking.rows:
            return ToolExecutionResult(
                content=json.dumps({"error": "No players matched those filters."})
            )
        return ToolExecutionResult(
            content=ranking.model_dump_json(),
            widget_data=ranking.model_dump(mode="json", by_alias=True),
        )

    return get_player_ranking_handler
