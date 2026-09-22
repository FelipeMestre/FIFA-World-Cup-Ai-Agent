from typing import Annotated, Literal

from pydantic import BaseModel, Field

from src.infra.openrouter import schemas as openrouter_schemas


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    content: str


class TeamWidgetPart(BaseModel):
    """`data` is `TeamAnalysis.model_dump(mode="json", by_alias=True)` --
    already camelCased for the frontend's `TeamSummary` contract, kept as a
    plain `dict` here rather than re-declaring the shape in the API layer.
    """

    type: Literal["team_widget"] = "team_widget"
    data: dict


class MatchWidgetPart(BaseModel):
    """`data` is `MatchAnalysis.model_dump(mode="json", by_alias=True)` --
    already camelCased for the frontend's `MatchSummary` contract, kept as a
    plain `dict` here rather than re-declaring the shape in the API layer.
    """

    type: Literal["match_widget"] = "match_widget"
    data: dict


class PlayerWidgetPart(BaseModel):
    """`data` is `PlayerAnalysis.model_dump(mode="json", by_alias=True)` --
    already camelCased for the frontend's `PlayerSummary` contract, kept as
    a plain `dict` here rather than re-declaring the shape in the API layer.
    """

    type: Literal["player_widget"] = "player_widget"
    data: dict


class CompareWidgetPart(BaseModel):
    """`data` is `PlayerComparison.model_dump(mode="json", by_alias=True)` --
    already camelCased for the frontend's `PlayerComparison` contract, kept
    as a plain `dict` here rather than re-declaring the shape in the API
    layer (same convention as `TeamWidgetPart`/`PlayerWidgetPart`). Produced
    by the `get_player_comparison` chat tool.
    """

    type: Literal["compare_widget"] = "compare_widget"
    data: dict


MessagePart = Annotated[
    TextPart | TeamWidgetPart | MatchWidgetPart | PlayerWidgetPart | CompareWidgetPart,
    Field(discriminator="type"),
]


class ChatReply(BaseModel):
    parts: list[MessagePart]


class SendMessageRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    conversation_id: str
    reply: ChatReply


class ReasoningDeltaEventDto(BaseModel):
    """SSE `reasoning_delta` event: one incremental piece of the model's
    reasoning trace."""

    type: Literal[openrouter_schemas.ChatStreamEventType.REASONING_DELTA] = (
        openrouter_schemas.ChatStreamEventType.REASONING_DELTA
    )
    content: str


class ContentDeltaEventDto(BaseModel):
    """SSE `content_delta` event: one incremental piece of the model's
    final-answer content."""

    type: Literal[openrouter_schemas.ChatStreamEventType.CONTENT_DELTA] = (
        openrouter_schemas.ChatStreamEventType.CONTENT_DELTA
    )
    content: str


class ToolCallEventDto(BaseModel):
    """SSE `tool_call` event: the tool-execution loop is dispatching a
    requested tool call."""

    type: Literal[openrouter_schemas.ChatStreamEventType.TOOL_CALL] = (
        openrouter_schemas.ChatStreamEventType.TOOL_CALL
    )
    name: str


class WidgetReadyEventDto(BaseModel):
    """SSE `widget_ready` event: a widget-producing tool call resolved
    inside the loop. `part` is the same shape a `message_done` event's
    `parts` will carry for this widget -- sent early so the frontend can
    render it without waiting for the rest of the turn.
    """

    type: Literal[openrouter_schemas.ChatStreamEventType.WIDGET_READY] = (
        openrouter_schemas.ChatStreamEventType.WIDGET_READY
    )
    part: MessagePart


class CapReachedEventDto(BaseModel):
    """SSE `cap_reached` event: the tool loop's iteration cap tripped.
    Carries the best-effort partial content plus a clarification ask. Always
    followed by a `message_done` event carrying the same combined text.
    """

    type: Literal[openrouter_schemas.ChatStreamEventType.CAP_REACHED] = (
        openrouter_schemas.ChatStreamEventType.CAP_REACHED
    )
    content: str
    clarification: str


class MessageDoneEventDto(BaseModel):
    """SSE `message_done` event: the terminal event for one chat turn. The
    conversation has been persisted and `parts` carries the final rendered
    message."""

    type: Literal[openrouter_schemas.ChatStreamEventType.MESSAGE_DONE] = (
        openrouter_schemas.ChatStreamEventType.MESSAGE_DONE
    )
    conversation_id: str
    parts: list[MessagePart]
    model: str | None = None


class ErrorEventDto(BaseModel):
    """SSE `error` event: the chat assistant failed mid-stream. Emitted
    instead of an HTTP error status because the response has already
    committed to `200 OK` by the time streaming begins."""

    type: Literal[openrouter_schemas.ChatStreamEventType.ERROR] = (
        openrouter_schemas.ChatStreamEventType.ERROR
    )
    detail: str


ChatStreamEvent = Annotated[
    ReasoningDeltaEventDto
    | ContentDeltaEventDto
    | ToolCallEventDto
    | WidgetReadyEventDto
    | CapReachedEventDto
    | MessageDoneEventDto
    | ErrorEventDto,
    Field(discriminator="type"),
]
