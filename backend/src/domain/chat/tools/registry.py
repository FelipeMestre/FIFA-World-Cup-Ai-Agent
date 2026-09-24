"""Tool registry for the bounded tool-execution loop.

Two tiers:

- `STATIC_TOOL_REGISTRY` -- tools whose handler needs no request-scoped
  dependency (currently just the dummy `get_current_utc_time`). Safe to
  build once at import time.
- `build_tool_registry(...)` -- assembles the full per-request registry,
  adding any tool whose handler is bound to a request-scoped dependency
  (currently `get_team_analysis`, bound to an `AsyncSession`-backed
  repository). Called from the conversation live socket
  (`src/api/v1/chat/routers/live_router.py`), once per send, the same way
  `get_national_team_repository` et al. are -- never at import time, since
  the session it closes over doesn't exist yet then.

`ALL_TOOL_SCHEMAS` covers every tool regardless of tier: a JSON schema
carries no dependency, so it's fine to list statically and send to every
request as the default `tools` payload.
"""

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from src.domain.chat.tools.get_current_utc_time import (
    GET_CURRENT_UTC_TIME_SCHEMA,
    GetCurrentUtcTimeArgs,
    get_current_utc_time_handler,
)
from src.domain.chat.tools.get_match_analysis import (
    GET_MATCH_ANALYSIS_SCHEMA,
    GetMatchAnalysisArgs,
    build_get_match_analysis_handler,
)
from src.domain.chat.tools.get_player_analysis import (
    GET_PLAYER_ANALYSIS_SCHEMA,
    GetPlayerAnalysisArgs,
    build_get_player_analysis_handler,
)
from src.domain.chat.tools.get_player_comparison import (
    GET_PLAYER_COMPARISON_SCHEMA,
    GetPlayerComparisonArgs,
    build_get_player_comparison_handler,
)
from src.domain.chat.tools.get_player_ranking import (
    GET_PLAYER_RANKING_SCHEMA,
    GetPlayerRankingArgs,
    build_get_player_ranking_handler,
)
from src.domain.chat.tools.get_team_analysis import (
    GET_TEAM_ANALYSIS_SCHEMA,
    GetTeamAnalysisArgs,
    build_get_team_analysis_handler,
)
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.infra.postgres.interfaces.match_analytics_repository_interface import (
    MatchAnalyticsRepositoryInterface,
)
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)
from src.infra.postgres.interfaces.team_analytics_repository_interface import (
    TeamAnalyticsRepositoryInterface,
)


class ToolDefinition(BaseModel):
    """Pairs one tool's OpenAI/OpenRouter tool-calling JSON schema with its
    Pydantic v2 argument-validation model and async handler.

    `widget_type` is the tool's fixed presentation identifier (e.g.
    `"team_widget"` for `get_team_analysis`), used by `ToolCallExecutor` to
    tag a successful call's `widget_data` -- `None` for a tool with no
    widget, like `get_current_utc_time`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    json_schema: dict
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[ToolExecutionResult]]
    widget_type: str | None = None


STATIC_TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "get_current_utc_time": ToolDefinition(
        json_schema=GET_CURRENT_UTC_TIME_SCHEMA,
        args_model=GetCurrentUtcTimeArgs,
        handler=get_current_utc_time_handler,
    ),
}

ALL_TOOL_SCHEMAS: list[dict] = [
    GET_CURRENT_UTC_TIME_SCHEMA,
    GET_TEAM_ANALYSIS_SCHEMA,
    GET_PLAYER_ANALYSIS_SCHEMA,
    GET_MATCH_ANALYSIS_SCHEMA,
    GET_PLAYER_COMPARISON_SCHEMA,
    GET_PLAYER_RANKING_SCHEMA,
]


def build_tool_registry(
    team_analytics_repository: TeamAnalyticsRepositoryInterface,
    player_analytics_repository: PlayerAnalyticsRepositoryInterface,
    match_analytics_repository: MatchAnalyticsRepositoryInterface,
) -> dict[str, ToolDefinition]:
    """Assembles the full tool registry for one request. Merges the static
    tier with every dependency-bound tool, freshly bound to this request's
    repositories.
    """
    return {
        **STATIC_TOOL_REGISTRY,
        "get_team_analysis": ToolDefinition(
            json_schema=GET_TEAM_ANALYSIS_SCHEMA,
            args_model=GetTeamAnalysisArgs,
            handler=build_get_team_analysis_handler(team_analytics_repository),
            widget_type="team_widget",
        ),
        "get_player_analysis": ToolDefinition(
            json_schema=GET_PLAYER_ANALYSIS_SCHEMA,
            args_model=GetPlayerAnalysisArgs,
            handler=build_get_player_analysis_handler(player_analytics_repository),
            widget_type="player_widget",
        ),
        "get_match_analysis": ToolDefinition(
            json_schema=GET_MATCH_ANALYSIS_SCHEMA,
            args_model=GetMatchAnalysisArgs,
            handler=build_get_match_analysis_handler(match_analytics_repository),
            widget_type="match_widget",
        ),
        "get_player_comparison": ToolDefinition(
            json_schema=GET_PLAYER_COMPARISON_SCHEMA,
            args_model=GetPlayerComparisonArgs,
            handler=build_get_player_comparison_handler(player_analytics_repository),
            widget_type="compare_widget",
        ),
        "get_player_ranking": ToolDefinition(
            json_schema=GET_PLAYER_RANKING_SCHEMA,
            args_model=GetPlayerRankingArgs,
            handler=build_get_player_ranking_handler(player_analytics_repository),
            widget_type="ranking_widget",
        ),
    }
