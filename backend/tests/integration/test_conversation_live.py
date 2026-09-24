"""Live conversation socket. Two clients on one conversation both receive the
accepted user message from the Redis stream, without a refresh. Uses real
Postgres and Redis. Auth is overridden; generation itself stays in
`generate_chat_reply_task` and is not what these tests wait for.
"""

import asyncio
import json
import socket
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest
import uvicorn
import websockets
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.domain.chat.services.chat_service import MessageDoneEvent
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.chat_message_repository import (
    _SqlAlchemyChatMessageRepository,
)
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_tasks import (
    serialize_chat_turn_event,
    turn_in_progress_key,
    turn_stream_key,
)
from src.main import app

_USER_ID = 990601
_OTHER_USER_ID = 990602
_ORIGIN = {"Origin": "http://localhost:3000"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def live_port() -> AsyncGenerator[int]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.02)
    else:
        server.should_exit = True
        await task
        raise RuntimeError("live socket server did not start")
    yield port
    server.should_exit = True
    await task


@pytest.fixture(autouse=True)
async def _seed_chat_users() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            # `name` is passed as its own bound parameter rather than derived
            # in SQL from a reused `:email` -- see the identical note in
            # `test_chat_service_start_turn.py` for why (pre-existing
            # asyncpg `AmbiguousParameterError`, unrelated to this task).
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, :name, 'hash', false, now())"
                ),
                {
                    "id": user_id,
                    "email": f"chat-live-test-{user_id}@example.test",
                    "name": f"chat-live-test-{user_id}",
                },
            )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_message_widget WHERE message_id IN "
                "(SELECT id FROM chat_message WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id IN (:a, :b)))"
            ),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_message WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id IN (:a, :b))"
            ),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM conversation WHERE user_id IN (:a, :b)"),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
        await cleanup_session.execute(
            text('DELETE FROM "user" WHERE id IN (:a, :b)'), {"a": _USER_ID, "b": _OTHER_USER_ID}
        )
        await cleanup_session.commit()


@pytest.fixture(autouse=True)
def _override_auth() -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": str(_USER_ID), "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    yield
    app.dependency_overrides.clear()


async def _socket_url(client: AsyncClient, port: int, conversation_id: str) -> str:
    response = await client.post(
        "/api/v1/chat/ws-tickets",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    ticket = response.json()["ticket"]
    return f"ws://127.0.0.1:{port}/api/v1/conversations/{conversation_id}/live?ticket={ticket}"


async def _cleanup_stream(conversation_id: str) -> None:
    await redis_client.delete(
        turn_in_progress_key(conversation_id), turn_stream_key(conversation_id)
    )


@pytest.mark.asyncio
async def test_a_send_on_one_socket_is_visible_on_another(
    client: AsyncClient, live_port: int
) -> None:
    conversation_id = str(uuid4())
    sender_url = await _socket_url(client, live_port, conversation_id)
    watcher_url = await _socket_url(client, live_port, conversation_id)

    async with (
        websockets.connect(sender_url, additional_headers=_ORIGIN) as sender,
        websockets.connect(watcher_url, additional_headers=_ORIGIN) as watcher,
    ):
        await sender.send(json.dumps({"type": "send", "message": "Hello from one window"}))
        sender_event = json.loads(await asyncio.wait_for(sender.recv(), timeout=5))
        watcher_event = json.loads(await asyncio.wait_for(watcher.recv(), timeout=5))

    assert sender_event["type"] == "user_message"
    assert watcher_event["type"] == "user_message"
    assert sender_event["content"] == "Hello from one window"
    assert watcher_event["content"] == "Hello from one window"
    assert sender_event["conversation_id"] == conversation_id
    assert await redis_client.get(turn_in_progress_key(conversation_id)) == "0-0"

    async with SessionFactory() as session:
        messages = await _SqlAlchemyChatMessageRepository(session).list_for_conversation(
            UUID(conversation_id), _USER_ID
        )
    assert [(message.sequence, message.role, message.content) for message in messages] == [
        (1, "user", "Hello from one window"),
    ]
    await _cleanup_stream(conversation_id)


@pytest.mark.asyncio
async def test_a_new_turn_does_not_replay_the_previous_reply(
    client: AsyncClient, live_port: int
) -> None:
    conversation_id = str(uuid4())
    await redis_client.xadd(
        turn_stream_key(conversation_id),
        serialize_chat_turn_event(
            MessageDoneEvent(
                conversation_id=conversation_id,
                content="previous turn",
                model=None,
                content_segments=["previous turn"],
            )
        ),
    )
    url = await _socket_url(client, live_port, conversation_id)
    async with websockets.connect(url, additional_headers=_ORIGIN) as socket:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(socket.recv(), timeout=0.4)
        await socket.send(json.dumps({"type": "send", "message": "Next question"}))
        event = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))

    assert event["type"] == "user_message"
    assert event["content"] == "Next question"
    await _cleanup_stream(conversation_id)


@pytest.mark.asyncio
async def test_a_second_send_is_rejected_while_a_turn_is_in_progress(
    client: AsyncClient, live_port: int
) -> None:
    conversation_id = str(uuid4())
    await redis_client.set(turn_in_progress_key(conversation_id), "1-0", ex=60)
    url = await _socket_url(client, live_port, conversation_id)

    async with websockets.connect(url, additional_headers=_ORIGIN) as socket:
        await socket.send(json.dumps({"type": "send", "message": "Should be rejected"}))
        event = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))

    assert event == {
        "type": "rejected",
        "detail": "A reply is already being generated for this conversation",
    }
    async with SessionFactory() as session:
        messages = await _SqlAlchemyChatMessageRepository(session).list_for_conversation(
            UUID(conversation_id), _USER_ID
        )
    assert messages == []
    await _cleanup_stream(conversation_id)


@pytest.mark.asyncio
async def test_another_user_cannot_join_the_live_socket(
    client: AsyncClient, live_port: int
) -> None:
    conversation_id = str(uuid4())
    owner_url = await _socket_url(client, live_port, conversation_id)
    async with websockets.connect(owner_url, additional_headers=_ORIGIN) as owner:
        await owner.send(json.dumps({"type": "send", "message": "First message"}))
        await asyncio.wait_for(owner.recv(), timeout=5)

    app.dependency_overrides[parse_jwt_data] = lambda: {
        "sub": str(_OTHER_USER_ID),
        "is_admin": False,
    }
    intruder_url = await _socket_url(client, live_port, conversation_id)
    with pytest.raises(websockets.exceptions.InvalidStatus):
        async with websockets.connect(intruder_url, additional_headers=_ORIGIN):
            pass

    await _cleanup_stream(conversation_id)
