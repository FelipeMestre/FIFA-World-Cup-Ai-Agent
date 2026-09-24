"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): the admin-only real_player search
endpoint backing the identity-link "correct match" picker.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.main import app

_REAL_PLAYER_ID = 990501


async def _admin_token_data() -> dict:
    return {"sub": "990501", "is_admin": True}


@pytest.fixture
async def seeded_real_player() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO real_player "
                "(player_id, first_name, last_name, position, profile_url, last_synced_at) "
                "VALUES (:id, 'Kylian', 'Mbappe', 'Forward', "
                "'https://example.test/mbappe', now())"
            ),
            {"id": _REAL_PLAYER_ID},
        )
        await session.commit()
        yield
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM real_player WHERE player_id = :id"), {"id": _REAL_PLAYER_ID}
        )
        await session.commit()


@pytest.mark.asyncio
async def test_search_returns_matching_real_players(
    client: AsyncClient, seeded_real_player: None
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/real-players/search", params={"q": "mbap"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    ids = [item["player_id"] for item in response.json()]
    assert _REAL_PLAYER_ID in ids


@pytest.mark.asyncio
async def test_search_requires_admin(client: AsyncClient, seeded_real_player: None) -> None:
    async def _non_admin() -> dict:
        return {"sub": "990501", "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = _non_admin

    response = await client.get("/api/v1/admin/real-players/search", params={"q": "mbap"})

    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_rejects_a_query_shorter_than_two_characters(client: AsyncClient) -> None:
    # A 1-character query would ILIKE-scan nearly every real_player row --
    # rejected at the request boundary rather than silently executed.
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/real-players/search", params={"q": "m"})

    app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_rejects_a_limit_above_the_server_cap(
    client: AsyncClient, seeded_real_player: None
) -> None:
    # Caps how many rows a single request can pull, regardless of what a
    # caller asks for -- the picker only ever needs one page of candidates.
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get(
        "/api/v1/admin/real-players/search", params={"q": "mbap", "limit": 500}
    )

    app.dependency_overrides.clear()
    assert response.status_code == 422
