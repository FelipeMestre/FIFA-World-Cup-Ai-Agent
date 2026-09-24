"""`get_team_analysis` -- the first real (non-dummy) analytics tool, and the
first one with a widget: `ToolExecutionResult.widget_data` carries the same
`TeamAnalysis`, reshaped (camelCase, via the model's alias generator) for
the frontend's `TeamWidgetPart`.

Unlike `get_current_utc_time`, this tool needs a database session, which is
request-scoped -- it can't be closed over at import time the way
`STATIC_TOOL_REGISTRY` builds its handlers. `build_get_team_analysis_handler`
takes the repository and returns a handler matching the
`Callable[[BaseModel], Awaitable[ToolExecutionResult]]` shape
`ToolDefinition.handler` expects.

It's registered per request instead: `domain.chat.tools.registry.build_tool_registry`
binds this handler to the request's `TeamAnalyticsRepositoryInterface`, and
the conversation live socket calls `build_tool_registry` while assembling
`ChatService` for one send -- the same per-request-assembly shape as any other repository-backed
dependency in this codebase, just applied to a tool handler instead of a
router.
"""

import json

from pydantic import BaseModel, ConfigDict, Field

from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.infra.postgres.interfaces.team_analytics_repository_interface import (
    TeamAnalyticsRepositoryInterface,
)

GET_TEAM_ANALYSIS_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_team_analysis",
        "description": (
            "Return a national team's full FIFA World Cup 2026 tournament record: "
            "match-by-match results, goals for/against, possession and other match "
            "stats compared against the tournament-wide average, and disciplinary "
            "totals. Use this whenever the user asks about a specific team's "
            "performance, form, or stats in the tournament."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": (
                        "The national team's name or FIFA code as the user referred to "
                        "it, e.g. 'Argentina' or 'ARG'."
                    ),
                }
            },
            "required": ["team_name"],
            "additionalProperties": False,
        },
    },
}


class GetTeamAnalysisArgs(BaseModel):
    """`extra='forbid'` rejects any unexpected argument the model
    hallucinates, so `ToolCallExecutor` can reject it via `ValidationError`.
    """

    model_config = ConfigDict(extra="forbid")

    team_name: str = Field(min_length=1, max_length=128)


def build_get_team_analysis_handler(repository: TeamAnalyticsRepositoryInterface):
    async def get_team_analysis_handler(args: GetTeamAnalysisArgs) -> ToolExecutionResult:
        analysis = await repository.get_team_analysis(args.team_name)
        if analysis is None:
            return ToolExecutionResult(
                content=json.dumps({"error": f"No team found matching '{args.team_name}'."})
            )
        return ToolExecutionResult(
            content=analysis.model_dump_json(),
            widget_data=analysis.model_dump(mode="json", by_alias=True),
        )

    return get_team_analysis_handler
