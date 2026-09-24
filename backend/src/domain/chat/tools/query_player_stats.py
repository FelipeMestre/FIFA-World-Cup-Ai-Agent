"""`query_player_stats` -- allowlisted filter/sort over player stats.

Infer dataset, competition, seasons, and filters from the request when they
are clear. A named club league means club_seasons — never ask World Cup vs
club. Ask in assistant text only for what is still missing. World Cup numbers
and club season numbers are never mixed into one score.
"""

import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.chat.exceptions.chat_exceptions import RankingQueryError
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.domain.player_analytics.competition_names import (
    competition_name,
    resolve_competition_id,
)
from src.domain.player_analytics.model.player_ranking import (
    FIELD_VALUES,
    GK_ONLY_FIELDS,
    STRING_EQ_FIELDS,
    FilterOp,
    PlayerStatField,
    QueryDataset,
    QueryPlayerStatsRequest,
    SortDir,
    StatFilter,
    field_allowed_on_dataset,
    format_season_label,
    normalize_season_years,
    used_fields,
)
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)

_FILTER_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "field": {
            "type": "string",
            "enum": FIELD_VALUES,
            "description": "Allowlisted column or derived stat.",
        },
        "op": {
            "type": "string",
            "enum": ["eq", "gte", "lte"],
            "description": "eq / gte / lte. position and nationality only support eq.",
        },
        "value": {
            "description": (
                "Number for stats; GK/DEF/MID/FWD for position; "
                "team name or FIFA code for nationality."
            ),
        },
    },
    "required": ["field", "op", "value"],
    "additionalProperties": False,
}

QUERY_PLAYER_STATS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "query_player_stats",
        "description": (
            "Return a sorted, filtered list of Football Players. "
            "Two datasets that must never be mixed: world_cup uses tournament "
            "player_stat only; club_seasons sums club season stats for players"
            "Infer arguments from the request and call. A named club league "
            "or competition (Spanish league, La Liga, Premier League, "
            "Champions League, …) means dataset=club_seasons and that "
            "competition — never ask whether they meant World Cup. Use "
            "world_cup only when they ask about the tournament. Ask in chat "
            "only for what is still genuinely missing. "
            "Pass seasons yourself (current season if unnamed). "
            "Top 5 → limit 5. Goalkeepers → position eq GK. "
            "Club seasons have no saves, clean sheets, or goals conceded "
            "(World Cup only). For club keepers, do not offer those fields; "
            "Shared fields: position, age, height_cm, nationality, appearances, "
            "minutes, goals, assists, goal_contributions, goals_per90, assists_per90, "
            "goal_contributions_per90, yellow_cards, red_cards. "
            "World Cup only: starts, penalty_goals, saves, saves_per90, "
            "clean_sheets, goals_conceded, goals_conceded_per90. "
            "Do not offer shots, shots on target, average rating, or a blended "
            "World Cup + club score. Put extra constraints in filters "
            "Do not claim a filter was applied unless you passed it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "enum": ["world_cup", "club_seasons"],
                    "description": (
                        "Infer from the request. Named club league/competition "
                        "= club_seasons. Tournament/World Cup = world_cup. "
                        "Never mix the two."
                    ),
                },
                "sort_by": {
                    "type": "string",
                    "enum": FIELD_VALUES,
                    "description": "Allowlisted field to sort by. Must exist on dataset.",
                },
                "sort_dir": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Default desc. Use asc for fewest cards or fewest conceded.",
                },
                "filters": {
                    "type": "array",
                    "items": _FILTER_ITEM_SCHEMA,
                    "description": "Optional allowlisted predicates applied in SQL.",
                },
                "seasons": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Required for club_seasons. Forbidden for world_cup. "
                        "You set this from the user's request: one or more labels "
                        "to include and sum, e.g. ['24/25'] or ['23/24', '24/25']. "
                        "Accepts 24/25, 2024/25, or 2024. Translate phrases like "
                        "'this season' or 'last two seasons' into those labels. "
                        "If they did not name a season, pass the current club season. "
                        "Do not pass latest/last_three and do not ask them to choose."
                    ),
                },
                "competition": {
                    "type": "string",
                    "description": (
                        "Required for club_seasons. Infer from the request: "
                        "'all' or a name/code/alias (Spanish league, La Liga, "
                        "ES1, Premier League, GB1, Champions League, CL, …)."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "How many players to return (1-25, default 10).",
                },
            },
            "required": ["dataset", "sort_by"],
            "additionalProperties": False,
        },
    },
}


class QueryFilterArg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: PlayerStatField
    op: FilterOp
    value: str | int | float


class QueryPlayerStatsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: QueryDataset
    sort_by: PlayerStatField
    sort_dir: SortDir = SortDir.DESC
    filters: list[QueryFilterArg] = Field(default_factory=list, max_length=12)
    seasons: list[str] = Field(default_factory=list, max_length=8)
    competition: str | None = Field(default=None, min_length=1, max_length=128)
    limit: int = Field(default=10, ge=1, le=25)

    @model_validator(mode="after")
    def validate_dataset_fields(self) -> "QueryPlayerStatsArgs":
        stat_filters = tuple(
            StatFilter(field=item.field, op=item.op, value=item.value) for item in self.filters
        )
        fields = used_fields(self.sort_by, stat_filters)
        for field in fields:
            if not field_allowed_on_dataset(field, self.dataset):
                raise ValueError(
                    f"'{field}' is not available on {self.dataset}. "
                    "World Cup-only fields: starts, penalty_goals, saves, "
                    "saves_per90, clean_sheets, goals_conceded, goals_conceded_per90."
                )
            if field in STRING_EQ_FIELDS:
                for item in self.filters:
                    if item.field == field and item.op != FilterOp.EQ:
                        raise ValueError(f"'{field}' only supports op=eq.")
        position = _position_eq(stat_filters)
        if fields & GK_ONLY_FIELDS and position is not None and position != "GK":
            raise ValueError(
                "saves / clean sheets / goals conceded are goalkeeper-only; "
                "set position to GK or omit it."
            )
        if self.dataset == QueryDataset.CLUB_SEASONS:
            if not self.seasons or self.competition is None:
                raise ValueError("seasons and competition are required for club_seasons.")
            if normalize_season_years(self.seasons) is None:
                raise ValueError(
                    "Each season must look like 24/25, 2024/25, or 2024. "
                    "Do not pass latest or last_three."
                )
            return self
        if self.seasons or self.competition is not None:
            raise ValueError("seasons and competition apply only to club_seasons.")
        return self


def _position_eq(filters: tuple[StatFilter, ...]) -> str | None:
    for item in filters:
        if item.field == PlayerStatField.POSITION:
            return str(item.value).strip().upper()
    return None


def _to_request(args: QueryPlayerStatsArgs) -> QueryPlayerStatsRequest:
    competition_id: str | None = None
    competition_label = "all competitions"
    season_years: tuple[int, ...] = ()
    season_label = ""
    if args.dataset == QueryDataset.CLUB_SEASONS:
        assert args.competition is not None
        parsed = normalize_season_years(args.seasons)
        if parsed is None or not parsed:
            raise RankingQueryError("Each season must look like 24/25, 2024/25, or 2024.")
        season_years = parsed
        season_label = format_season_label(parsed)
        if args.competition.strip().casefold() != "all":
            competition_id = resolve_competition_id(args.competition)
            if competition_id is None:
                raise RankingQueryError(
                    f"No competition matching '{args.competition}'. "
                    "Use 'all' or a known name such as Premier League or Champions League."
                )
            competition_label = competition_name(competition_id)
    return QueryPlayerStatsRequest(
        dataset=args.dataset,
        sort_by=args.sort_by,
        sort_dir=args.sort_dir,
        filters=tuple(
            StatFilter(field=item.field, op=item.op, value=item.value) for item in args.filters
        ),
        season_years=season_years,
        season_label=season_label,
        competition_id=competition_id,
        competition_label=competition_label,
        limit=args.limit,
    )


def build_query_player_stats_handler(repository: PlayerAnalyticsRepositoryInterface):
    async def query_player_stats_handler(args: QueryPlayerStatsArgs) -> ToolExecutionResult:
        try:
            request = _to_request(args)
            ranking = await repository.query_player_stats(request)
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

    return query_player_stats_handler
