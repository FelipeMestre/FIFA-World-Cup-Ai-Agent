from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import (
    ChatReply,
    SendMessageRequest,
    SendMessageResponse,
    TextPart,
)
from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.services.chat_service import ChatService
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(
    conversation_cache: Annotated[
        ConversationCacheRepositoryInterface, Depends(get_conversation_cache_repository)
    ],
    openrouter_client: Annotated[OpenRouterClientInterface, Depends(get_openrouter_client)],
) -> ChatService:
    return ChatService(conversation_cache, openrouter_client)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.post(
    "/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a chat message",
    description="Sends a user message to the World Cup AI Scout assistant and returns its reply.",
    responses={
        status.HTTP_502_BAD_GATEWAY: {"description": "The chat assistant is unavailable"},
    },
)
async def send_message(
    payload: SendMessageRequest,
    chat_service: ChatServiceDep,
    _: JwtDataDep,
) -> SendMessageResponse:
    try:
        conversation_id, reply_text = await chat_service.send_message(
            conversation_id=payload.conversation_id,
            user_message=payload.message,
        )
    except ChatServiceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The chat assistant is temporarily unavailable",
        ) from exc
    return SendMessageResponse(
        conversation_id=conversation_id,
        reply=ChatReply(parts=[TextPart(content=reply_text)]),
    )
