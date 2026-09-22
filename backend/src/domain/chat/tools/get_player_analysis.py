"""`get_player_analysis` -- the player-level counterpart to
`get_team_analysis`. Same shape: `ToolExecutionResult.widget_data` carries
the same `PlayerAnalysis`, reshaped (camelCase, via the model's alias
generator) for the frontend's `PlayerWidgetPart`.

Like `get_team_analysis`, this tool needs a database session, which is
request-scoped -- `build_get_player_analysis_handler` takes the repository
and returns a handler matching the
`Callable[[BaseModel], Awaitable[ToolExecutionResult]]` shape
`ToolDefinition.handler` expects. It's registered per request from
`domain.chat.tools.registry.build_tool_registry`, bound to the request's
`PlayerAnalyticsRepositoryInterface`.
"""

import json

from pydantic import BaseModel, ConfigDict, Field

from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)

GET_PLAYER_ANALYSIS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_player_analysis",
        "description": (
            "Return one player's FIFA World Cup 2026 tournament record: appearances, "
            "minutes, goals, assists, cards, and goalkeeper stats where applicable, "
            "each broken down as totals and per-90 rates with percentiles against "
            "other players at the same position, plus a stats-derived contribution "
            "tier and discipline read. Use this whenever the user asks about a "
            "specific player's performance, form, role, or stats in the tournament."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": (
                        "The player's name as the user referred to it, e.g. "
                        "'Lionel Messi' or 'Messi'."
                    ),
                }
            },
            "required": ["player_name"],
            "additionalProperties": False,
        },
    },
}


class GetPlayerAnalysisArgs(BaseModel):
    """`extra='forbid'` rejects any unexpected argument the model
    hallucinates, so `ToolCallExecutor` can reject it via `ValidationError`.
    """

    model_config = ConfigDict(extra="forbid")

    player_name: str = Field(min_length=1, max_length=128)


def build_get_player_analysis_handler(repository: PlayerAnalyticsRepositoryInterface):
    async def get_player_analysis_handler(args: GetPlayerAnalysisArgs) -> ToolExecutionResult:
        analysis = await repository.get_player_analysis(args.player_name)
        if analysis is None:
            return ToolExecutionResult(
                content=json.dumps({"error": f"No player found matching '{args.player_name}'."})
            )
        return ToolExecutionResult(
            content=analysis.model_dump_json(),
            widget_data=analysis.model_dump(mode="json", by_alias=True),
        )

    return get_player_analysis_handler
