"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table).
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.main import app

_ADMIN_USER_ID = 990301
_REAL_PLAYER_ID = 990301


async def _admin_token_data() -> dict:
    return {"sub": str(_ADMIN_USER_ID), "is_admin": True}


@pytest.fixture
async def pending_link() -> AsyncGenerator[dict]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, split_part(:email, '@', 1), 'hash', true, now())"
            ),
            {"id": _ADMIN_USER_ID, "email": "admin-identity-link-test@example.test"},
        )
        player_id = (
            await session.execute(text("SELECT player_id FROM player LIMIT 1"))
        ).scalar_one()
        await session.execute(
            text(
                "INSERT INTO real_player "
                "(player_id, first_name, last_name, position, profile_url, last_synced_at) "
                "VALUES (:id, 'Test', 'Player', 'Forward', 'https://example.test', now())"
            ),
            {"id": _REAL_PLAYER_ID},
        )
        link_id = (
            await session.execute(
                text(
                    "INSERT INTO player_identity_link "
                    "(player_id, real_player_id, match_method, match_confidence, "
                    "reviewed_by_admin, status) "
                    "VALUES (:player_id, :real_player_id, 'FUZZY_NAME', 0.900, "
                    "false, 'PENDING') "
                    "RETURNING id"
                ),
                {"player_id": player_id, "real_player_id": _REAL_PLAYER_ID},
            )
        ).scalar_one()
        await session.commit()
        yield {"link_id": link_id, "player_id": player_id}
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM player_identity_link WHERE id = :id"), {"id": link_id}
        )
        await session.execute(
            text("DELETE FROM real_player WHERE player_id = :id"), {"id": _REAL_PLAYER_ID}
        )
        await session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _ADMIN_USER_ID})
        await session.commit()


@pytest.mark.asyncio
async def test_list_pending_includes_seeded_link(client: AsyncClient, pending_link: dict) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/identity-links/pending")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert pending_link["link_id"] in ids


@pytest.mark.asyncio
async def test_approve_pending_link_sets_status_approved(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(f"/api/v1/admin/identity-links/{pending_link['link_id']}/approve")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_already_reviewed_link_returns_409(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    await client.post(f"/api/v1/admin/identity-links/{pending_link['link_id']}/reject")
    second_response = await client.post(
        f"/api/v1/admin/identity-links/{pending_link['link_id']}/approve"
    )

    app.dependency_overrides.clear()
    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_approve_unknown_link_returns_404(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post("/api/v1/admin/identity-links/999999999/approve")

    app.dependency_overrides.clear()
    assert response.status_code == 404
