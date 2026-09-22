"""`get_player_comparison` -- the two-player counterpart to
`get_player_analysis`. Same shape: `ToolExecutionResult.widget_data` carries
a `PlayerComparison`, reshaped (camelCase, via the model's alias generator)
for the frontend's `CompareWidgetPart`.

Like `get_player_analysis`, this tool needs a database session, which is
request-scoped -- `build_get_player_comparison_handler` takes the
repository and returns a handler matching the
`Callable[[BaseModel], Awaitable[ToolExecutionResult]]` shape
`ToolDefinition.handler` expects. It's registered per request from
`domain.chat.tools.registry.build_tool_registry`, bound to the request's
`PlayerAnalyticsRepositoryInterface`.

Unlike `get_player_analysis` (which returns `None` for an unmatched single
player), `PlayerAnalyticsRepositoryInterface.get_player_comparison` raises
`PlayerNotFoundError`/`SamePlayerComparisonError` -- resolving two players
in one call means a bare `None` couldn't say which side failed, or why.
"""

import json

from pydantic import BaseModel, ConfigDict, Field

from src.domain.chat.exceptions.chat_exceptions import (
    PlayerNotFoundError,
    SamePlayerComparisonError,
)
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)

GET_PLAYER_COMPARISON_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_player_comparison",
        "description": (
            "Compare two players' FIFA World Cup 2026 tournament records side by side: "
            "per-90 rates for goals, assists, goal contribution, cards, and goalkeeper "
            "stats where applicable, each with a percentile computed against other "
            "players at that player's own position (positions may differ between the "
            "two), plus a short natural-language summary of the biggest differences. "
            "Use this whenever the user asks to compare two specific players, or asks "
            "who is better at something between two named players."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "player_a_name": {
                    "type": "string",
                    "description": (
                        "The first player's name as the user referred to it, e.g. "
                        "'Lionel Messi' or 'Messi'."
                    ),
                },
                "player_b_name": {
                    "type": "string",
                    "description": (
                        "The second player's name as the user referred to it, e.g. "
                        "'Kylian Mbappe' or 'Mbappe'."
                    ),
                },
            },
            "required": ["player_a_name", "player_b_name"],
            "additionalProperties": False,
        },
    },
}


class GetPlayerComparisonArgs(BaseModel):
    """`extra='forbid'` rejects any unexpected argument the model
    hallucinates, so `ToolCallExecutor` can reject it via `ValidationError`.
    """

    model_config = ConfigDict(extra="forbid")

    player_a_name: str = Field(min_length=1, max_length=128)
    player_b_name: str = Field(min_length=1, max_length=128)


def build_get_player_comparison_handler(repository: PlayerAnalyticsRepositoryInterface):
    async def get_player_comparison_handler(args: GetPlayerComparisonArgs) -> ToolExecutionResult:
        try:
            comparison = await repository.get_player_comparison(
                args.player_a_name, args.player_b_name
            )
        except PlayerNotFoundError as exc:
            return ToolExecutionResult(content=json.dumps({"error": str(exc)}))
        except SamePlayerComparisonError as exc:
            return ToolExecutionResult(content=json.dumps({"error": str(exc)}))

        return ToolExecutionResult(
            content=comparison.model_dump_json(),
            widget_data=comparison.model_dump(mode="json", by_alias=True),
        )

    return get_player_comparison_handler
