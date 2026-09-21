"""Dummy tool proving the tool-calling harness end-to-end.

`get_current_utc_time` performs no I/O beyond reading the current UTC clock
-- no repository, database, or real team/match/player data access, and has
no widget of its own (`ToolExecutionResult.widget_data` stays `None`).
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from src.domain.chat.tools.tool_execution_result import ToolExecutionResult

GET_CURRENT_UTC_TIME_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "get_current_utc_time",
        "description": "Return the current UTC date and time in ISO-8601 format.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


class GetCurrentUtcTimeArgs(BaseModel):
    """Empty-args model -- `get_current_utc_time` takes no parameters.

    `extra="forbid"` rejects any unexpected argument the model hallucinates,
    so `ToolCallExecutor` can reject it gracefully via `ValidationError`.
    """

    model_config = ConfigDict(extra="forbid")


async def get_current_utc_time_handler(_args: GetCurrentUtcTimeArgs) -> ToolExecutionResult:
    return ToolExecutionResult(content=datetime.now(UTC).isoformat())
