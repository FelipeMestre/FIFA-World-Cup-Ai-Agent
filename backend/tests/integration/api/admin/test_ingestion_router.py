"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): overrides `parse_jwt_data` so
`require_admin`'s own permission check still runs for real.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.main import app

_ADMIN_USER_ID = 990201
_NON_ADMIN_USER_ID = 990202


async def _admin_token_data() -> dict:
    return {"sub": str(_ADMIN_USER_ID), "is_admin": True}


async def _non_admin_token_data() -> dict:
    return {"sub": str(_NON_ADMIN_USER_ID), "is_admin": False}


@pytest.fixture(autouse=True)
async def _seed_users() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, split_part(:email, '@', 1), 'hash', :is_admin, now())"
            ),
            [
                {
                    "id": _ADMIN_USER_ID,
                    "email": "admin-ingestion-test@example.test",
                    "is_admin": True,
                },
                {
                    "id": _NON_ADMIN_USER_ID,
                    "email": "user-ingestion-test@example.test",
                    "is_admin": False,
                },
            ],
        )
        await session.commit()
    yield
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM ingestion_job WHERE requested_by_user_id IN (:a, :b)"),
            {"a": _ADMIN_USER_ID, "b": _NON_ADMIN_USER_ID},
        )
        await session.execute(
            text('DELETE FROM "user" WHERE id IN (:a, :b)'),
            {"a": _ADMIN_USER_ID, "b": _NON_ADMIN_USER_ID},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_upload_unknown_table_returns_400(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        "/api/v1/admin/ingestion/synthetic-upload",
        data={"table_name": "not_a_real_table"},
        files={"file": ("bad.csv", b"a,b\n1,2\n", "text/csv")},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_by_non_admin_returns_403(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _non_admin_token_data

    response = await client.post(
        "/api/v1/admin/ingestion/synthetic-upload",
        data={"table_name": "team"},
        files={"file": ("team.csv", b"a,b\n1,2\n", "text/csv")},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_known_table_creates_queued_job(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        "/api/v1/admin/ingestion/synthetic-upload",
        data={"table_name": "team"},
        files={"file": ("team.csv", b"a,b\n1,2\n", "text/csv")},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert isinstance(body["job_id"], int)


@pytest.mark.asyncio
async def test_get_unknown_job_returns_404(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.get("/api/v1/admin/ingestion/jobs/999999999")

    app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_sync_then_poll_status(client: AsyncClient) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    trigger_response = await client.post("/api/v1/admin/ingestion/transfermarkt-sync")
    job_id = trigger_response.json()["job_id"]
    status_response = await client.get(f"/api/v1/admin/ingestion/jobs/{job_id}")

    app.dependency_overrides.clear()
    assert trigger_response.status_code == 201
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["job_id"] == job_id
    assert body["job_type"] == "transfermarkt_sync"
    assert body["status"] == "queued"
