"""`get_match_analysis` -- the match-level counterpart to `get_team_analysis`
and `get_player_analysis`. `ToolExecutionResult.widget_data` carries the
same `MatchAnalysis`, reshaped (camelCase, via the model's alias generator)
for the frontend's `MatchWidgetPart`.

Unlike the other two tools, this one has a third outcome besides "found" /
"not found": the home/away (+ optional stage/date) query can resolve to more
than one match. That case returns `MatchAnalysisAmbiguous` from the
repository, which this handler serializes into the JSON `content` string
(never `widget_data`) so the model reads the candidate list back and asks
the user to disambiguate in its next reply -- the same tool-result-to-model
round-trip `content` already provides for the not-found case, no new
plumbing needed.

`build_get_match_analysis_handler` takes the repository and returns a
handler matching the `Callable[[BaseModel], Awaitable[ToolExecutionResult]]`
shape `ToolDefinition.handler` expects, the same request-scoped-dependency
pattern `get_team_analysis.py`/`get_player_analysis.py` use.
"""

import json

from pydantic import BaseModel, ConfigDict, Field

from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.domain.match_analytics.model.match_analysis import MatchAnalysisAmbiguous
from src.infra.postgres.interfaces.match_analytics_repository_interface import (
    MatchAnalyticsRepositoryInterface,
)

GET_MATCH_ANALYSIS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_match_analysis",
        "description": (
            "Return the full breakdown of one FIFA World Cup 2026 match between two "
            "national teams: scoreboard, scorers, possession/shots/other stats split, "
            "event timeline (goals, cards, VAR reviews), Player of the Match, and both "
            "teams' lineups by position. Use this whenever the user asks about a "
            "specific match, fixture, or result between two named teams. If the two "
            "teams played each other more than once (e.g. group stage and knockout "
            "stage), pass `stage` and/or `date` to pick the right one."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "home_team_name": {
                    "type": "string",
                    "description": (
                        "One of the two teams, as the user referred to it, e.g. "
                        "'Argentina' or 'ARG'. Doesn't need to be the actual home side "
                        "-- the match is looked up by team pair either way."
                    ),
                },
                "away_team_name": {
                    "type": "string",
                    "description": "The other team, as the user referred to it.",
                },
                "stage": {
                    "type": "string",
                    "description": (
                        "Optional tournament stage to disambiguate repeat fixtures "
                        "between the same two teams, e.g. 'Group Stage' or 'Final'."
                    ),
                },
                "date": {
                    "type": "string",
                    "description": (
                        "Optional match date to disambiguate repeat fixtures, as an "
                        "ISO 'YYYY-MM-DD' string."
                    ),
                },
            },
            "required": ["home_team_name", "away_team_name"],
            "additionalProperties": False,
        },
    },
}


class GetMatchAnalysisArgs(BaseModel):
    """`extra='forbid'` rejects any unexpected argument the model
    hallucinates, so `ToolCallExecutor` can reject it via `ValidationError`.
    """

    model_config = ConfigDict(extra="forbid")

    home_team_name: str = Field(min_length=1, max_length=128)
    away_team_name: str = Field(min_length=1, max_length=128)
    stage: str | None = Field(default=None, max_length=128)
    date: str | None = Field(default=None, max_length=32)


def build_get_match_analysis_handler(repository: MatchAnalyticsRepositoryInterface):
    async def get_match_analysis_handler(args: GetMatchAnalysisArgs) -> ToolExecutionResult:
        result = await repository.get_match_analysis(
            args.home_team_name, args.away_team_name, args.stage, args.date
        )
        if result is None:
            return ToolExecutionResult(
                content=json.dumps(
                    {
                        "error": (
                            f"No match found between '{args.home_team_name}' and "
                            f"'{args.away_team_name}'."
                        )
                    }
                )
            )
        if isinstance(result, MatchAnalysisAmbiguous):
            return ToolExecutionResult(content=result.model_dump_json())
        return ToolExecutionResult(
            content=result.model_dump_json(),
            widget_data=result.model_dump(mode="json", by_alias=True),
        )

    return get_match_analysis_handler
