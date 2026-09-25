"""`get_team_comparison` -- head-to-head of two national teams at the World Cup.

`ToolExecutionResult.widget_data` carries a `TeamComparison` in camelCase for
the `team_compare_widget` part. The same object is what the model reads back,
so it can talk about results, strengths, squad value, and the position groups.
"""

import json

from pydantic import BaseModel, ConfigDict, Field

from src.domain.chat.exceptions.chat_exceptions import SameTeamComparisonError, TeamNotFoundError
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.infra.postgres.interfaces.team_analytics_repository_interface import (
    TeamAnalyticsRepositoryInterface,
)

GET_TEAM_COMPARISON_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_team_comparison",
        "description": (
            "Compare two national teams across the FIFA World Cup 2026: results and "
            "how far each went, goal and xG rates, possession, chance quality, "
            "discipline, and cards, each against the other team and the tournament "
            "average. Also returns squad average age, estimated market value, FIFA "
            "rank, Elo, manager, group points, and a player-by-player comparison "
            "grouped GK vs GK, DEF vs DEF, MID vs MID, and FWD vs FWD. Use this "
            "whenever the user asks to compare two teams, or asks who is stronger "
            "between two named countries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "team_a_name": {
                    "type": "string",
                    "description": (
                        "The first national team's name or FIFA code, e.g. 'Argentina' or 'ARG'."
                    ),
                },
                "team_b_name": {
                    "type": "string",
                    "description": (
                        "The second national team's name or FIFA code, e.g. 'France' or 'FRA'."
                    ),
                },
            },
            "required": ["team_a_name", "team_b_name"],
            "additionalProperties": False,
        },
    },
}


class GetTeamComparisonArgs(BaseModel):
    """`extra='forbid'` rejects any unexpected argument the model
    hallucinates, so `ToolCallExecutor` can reject it via `ValidationError`.
    """

    model_config = ConfigDict(extra="forbid")

    team_a_name: str = Field(min_length=1, max_length=128)
    team_b_name: str = Field(min_length=1, max_length=128)


def build_get_team_comparison_handler(repository: TeamAnalyticsRepositoryInterface):
    async def get_team_comparison_handler(args: GetTeamComparisonArgs) -> ToolExecutionResult:
        try:
            comparison = await repository.get_team_comparison(args.team_a_name, args.team_b_name)
        except TeamNotFoundError as exc:
            return ToolExecutionResult(content=json.dumps({"error": str(exc)}))
        except SameTeamComparisonError as exc:
            return ToolExecutionResult(content=json.dumps({"error": str(exc)}))

        return ToolExecutionResult(
            content=comparison.model_dump_json(),
            widget_data=comparison.model_dump(mode="json", by_alias=True),
        )

    return get_team_comparison_handler
