"""Tool registry for the bounded tool-execution loop.

A plain `dict[str, ToolDefinition]` built at import time -- the simplest
structure that still generalizes when real tools are added later. Currently
holds exactly one dummy tool; adding a real analytics tool is out of scope
for this change.
"""

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from src.domain.chat.tools.get_current_utc_time import (
    GET_CURRENT_UTC_TIME_SCHEMA,
    GetCurrentUtcTimeArgs,
    get_current_utc_time_handler,
)


class ToolDefinition(BaseModel):
    """Pairs one tool's OpenAI/OpenRouter tool-calling JSON schema with its
    Pydantic v2 argument-validation model and async handler.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    json_schema: dict
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[str]]


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "get_current_utc_time": ToolDefinition(
        json_schema=GET_CURRENT_UTC_TIME_SCHEMA,
        args_model=GetCurrentUtcTimeArgs,
        handler=get_current_utc_time_handler,
    ),
}
