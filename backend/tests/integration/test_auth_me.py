"""Integration tests for GET /api/v1/auth/me against real Postgres."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.main import app

_USER_ID = 990901
_EMAIL = "me-endpoint-test@football.ai"
_NAME = "Ada Scout"


@pytest.fixture(autouse=True)
async def _seed_user() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, :name, 'hash', false, now())"
            ),
            {"id": _USER_ID, "email": _EMAIL, "name": _NAME},
        )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _USER_ID})
        await cleanup_session.commit()


@pytest.fixture(autouse=True)
def _override_auth() -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": str(_USER_ID), "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_me_returns_the_authenticated_users_name(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == _USER_ID
    assert body["email"] == _EMAIL
    assert body["name"] == _NAME
    assert body["is_admin"] is False


@pytest.mark.asyncio
async def test_me_returns_401_when_the_user_row_is_missing(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = lambda: {"sub": "999999001", "is_admin": False}

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 401
