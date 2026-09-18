from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    content: str


class TeamWidgetPart(BaseModel):
    """Not implemented yet -- defined for forward-compat with a future
    analytics-tool phase."""

    type: Literal["team_widget"] = "team_widget"
    data: dict


class MatchWidgetPart(BaseModel):
    """Not implemented yet."""

    type: Literal["match_widget"] = "match_widget"
    data: dict


class PlayerWidgetPart(BaseModel):
    """Not implemented yet."""

    type: Literal["player_widget"] = "player_widget"
    data: dict


class CompareWidgetPart(BaseModel):
    """Not implemented yet."""

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
