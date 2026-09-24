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
_OTHER_REAL_PLAYER_ID = 990302


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
        await session.execute(
            text(
                "INSERT INTO real_player "
                "(player_id, first_name, last_name, position, profile_url, last_synced_at) "
                "VALUES (:id, 'Other', 'Candidate', 'Midfield', "
                "'https://example.test/other', now())"
            ),
            {"id": _OTHER_REAL_PLAYER_ID},
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
            text("DELETE FROM real_player WHERE player_id IN (:id, :other_id)"),
            {"id": _REAL_PLAYER_ID, "other_id": _OTHER_REAL_PLAYER_ID},
        )
        await session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _ADMIN_USER_ID})
        await session.commit()


@pytest.mark.asyncio
async def test_list_pending_includes_seeded_link_with_comparison_data(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/identity-links")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["total"] >= 1
    items = body["items"]
    ids = [item["id"] for item in items]
    assert pending_link["link_id"] in ids
    seeded = next(item for item in items if item["id"] == pending_link["link_id"])
    assert seeded["synthetic_player"]["id"] == pending_link["player_id"]
    assert isinstance(seeded["synthetic_player"]["nationality"], str)
    assert seeded["synthetic_player"]["nationality"] != ""
    assert seeded["real_player"]["player_id"] == _REAL_PLAYER_ID
    assert seeded["real_player"]["first_name"] == "Test"


@pytest.mark.asyncio
async def test_list_pending_respects_limit_and_offset(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/identity-links", params={"limit": 1, "offset": 0})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) <= 1
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_pending_rejects_limit_above_server_cap(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/identity-links", params={"limit": 1000})

    app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_defaults_to_pending_only(client: AsyncClient, pending_link: dict) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    approve_response = await client.post(
        f"/api/v1/admin/identity-links/{pending_link['link_id']}/approve"
    )
    assert approve_response.status_code == 200

    response = await client.get("/api/v1/admin/identity-links")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert pending_link["link_id"] not in ids


@pytest.mark.asyncio
async def test_list_filters_by_status_query_param(client: AsyncClient, pending_link: dict) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    approve_response = await client.post(
        f"/api/v1/admin/identity-links/{pending_link['link_id']}/approve"
    )
    assert approve_response.status_code == 200

    approved_response = await client.get(
        "/api/v1/admin/identity-links", params={"status": "approved"}
    )
    pending_response = await client.get(
        "/api/v1/admin/identity-links", params={"status": "pending"}
    )

    app.dependency_overrides.clear()
    assert approved_response.status_code == 200
    assert pending_response.status_code == 200
    approved_ids = [item["id"] for item in approved_response.json()["items"]]
    pending_ids = [item["id"] for item in pending_response.json()["items"]]
    assert pending_link["link_id"] in approved_ids
    assert pending_link["link_id"] not in pending_ids


@pytest.mark.asyncio
async def test_list_rejects_invalid_status_value(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get(
        "/api/v1/admin/identity-links", params={"status": "not-a-real-status"}
    )

    app.dependency_overrides.clear()
    assert response.status_code == 422


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


@pytest.mark.asyncio
async def test_reassign_corrects_match_to_different_real_player(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        f"/api/v1/admin/identity-links/{pending_link['link_id']}/reassign",
        json={"real_player_id": _OTHER_REAL_PLAYER_ID},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["real_player_id"] == _OTHER_REAL_PLAYER_ID
    assert body["match_method"] == "manual"
    assert body["status"] == "approved"


@pytest.mark.asyncio
async def test_reassign_to_unknown_real_player_returns_404(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        f"/api/v1/admin/identity-links/{pending_link['link_id']}/reassign",
        json={"real_player_id": 999999999},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reassign_unknown_link_returns_404(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        "/api/v1/admin/identity-links/999999999/reassign",
        json={"real_player_id": _REAL_PLAYER_ID},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reassign_to_already_linked_real_player_returns_409(
    client: AsyncClient, pending_link: dict
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data
    # A second synthetic player already linked to _OTHER_REAL_PLAYER_ID, so
    # reassigning the seeded link onto it should conflict.
    other_team_id = 990303
    other_player_id = 990303
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, group_letter, "
                "confederation, fifa_ranking_pre_tournament, elo_rating, manager_name) "
                "VALUES (:id, 'Other Test Team', 'OTT', 'B', 'UEFA', 2, 1000, 'Other Manager')"
            ),
            {"id": other_team_id},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Other Synthetic Player', 'MF', 'Other Club', "
                "500000, 3, '1999-01-01', 175, 1)"
            ),
            {"id": other_player_id, "team_id": other_team_id},
        )
        await session.execute(
            text(
                "INSERT INTO player_identity_link "
                "(player_id, real_player_id, match_method, match_confidence, "
                "reviewed_by_admin, status) "
                "VALUES (:player_id, :real_player_id, 'FUZZY_NAME', 0.900, false, 'PENDING')"
            ),
            {"player_id": other_player_id, "real_player_id": _OTHER_REAL_PLAYER_ID},
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/admin/identity-links/{pending_link['link_id']}/reassign",
        json={"real_player_id": _OTHER_REAL_PLAYER_ID},
    )

    app.dependency_overrides.clear()
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM player_identity_link WHERE player_id = :id"),
            {"id": other_player_id},
        )
        await cleanup_session.execute(
            text("DELETE FROM player WHERE player_id = :id"), {"id": other_player_id}
        )
        await cleanup_session.execute(
            text("DELETE FROM national_team WHERE team_id = :id"), {"id": other_team_id}
        )
        await cleanup_session.commit()
    assert response.status_code == 409
