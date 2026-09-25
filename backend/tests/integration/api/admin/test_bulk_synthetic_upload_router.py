"""Integration tests for the bulk synthetic CSV upload endpoint, against a
real Postgres instance (no mocking, per AGENTS.md's testing anti-pattern
table). The actual worker execution (`bulk_synthetic_upload_task`) is
invoked directly against the real DB, the same precedent as
`test_task_error_handling.py` calling `_fail_job` directly, instead of
relying on the real Arq queue -- this repo's docker-compose worker container
shares this same Redis/Postgres and would otherwise race the test to process
the same enqueued job.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.infra.task_queue.tasks import bulk_synthetic_upload_task
from src.main import app

_ADMIN_USER_ID = 990301
_TEAM_ID = 990301
_PLAYER_ID = 990301

_TEAM_CSV = (
    b"team_id,team_name,fifa_code,group_letter,confederation,"
    b"fifa_ranking_pre_tournament,elo_rating,manager_name\n"
    b"990301,Bulk Test Team,BLK,A,UEFA,10,1500,Bulk Test Manager\n"
)
_PLAYER_CSV = (
    b"player_id,team_id,player_name,position,club_team,market_value_eur,"
    b"caps,date_of_birth,height_cm,goals\n"
    b"990301,990301,Bulk Test Player,FW,Bulk Test Club,1000000,10,2000-01-01,180,5\n"
)


async def _admin_token_data() -> dict:
    return {"sub": str(_ADMIN_USER_ID), "is_admin": True}


@pytest.fixture(autouse=True)
async def _seed_admin_user() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, :name, 'hash', :is_admin, now())"
            ),
            [
                {
                    "id": _ADMIN_USER_ID,
                    "email": "admin-bulk-ingestion-test@example.test",
                    "name": "admin-bulk-ingestion-test",
                    "is_admin": True,
                }
            ],
        )
        await session.commit()
    yield
    async with SessionFactory() as session:
        await session.execute(text("DELETE FROM player WHERE player_id = :id"), {"id": _PLAYER_ID})
        await session.execute(
            text("DELETE FROM national_team WHERE team_id = :id"), {"id": _TEAM_ID}
        )
        await session.execute(
            text("DELETE FROM ingestion_job WHERE requested_by_user_id = :id"),
            {"id": _ADMIN_USER_ID},
        )
        await session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _ADMIN_USER_ID})
        await session.commit()


@pytest.mark.asyncio
async def test_bulk_upload_scrambled_order_ingests_all_files_with_correct_row_counts(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    # Child-before-parent upload order -- the endpoint/task must still
    # ingest `team` before `player` internally (FK-safe order), regardless.
    response = await client.post(
        "/api/v1/admin/ingestion/bulk-synthetic-upload",
        files=[
            ("files", ("squads_and_players.csv", _PLAYER_CSV, "text/csv")),
            ("files", ("teams.csv", _TEAM_CSV, "text/csv")),
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    job_id = body["job_id"]
    file_results = {f["filename"]: f for f in body["files"]}
    assert file_results["squads_and_players.csv"] == {
        "filename": "squads_and_players.csv",
        "table_name": "player",
        "accepted": True,
        "reason": None,
    }
    assert file_results["teams.csv"] == {
        "filename": "teams.csv",
        "table_name": "team",
        "accepted": True,
        "reason": None,
    }

    # Simulate the worker directly against the real DB -- see module
    # docstring for why this bypasses the live Arq queue.
    await bulk_synthetic_upload_task(
        {},
        job_id,
        [("squads_and_players.csv", _PLAYER_CSV), ("teams.csv", _TEAM_CSV)],
    )

    status_response = await client.get(f"/api/v1/admin/ingestion/jobs/{job_id}")

    app.dependency_overrides.clear()
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["job_type"] == "bulk_synthetic_upload"
    assert status_body["status"] == "succeeded"
    assert status_body["row_counts"] == {"team": 1, "player": 1}
    # One stage checkpoint per ingested table, in the fixed FK-safe order
    # (team before player) regardless of upload order -- same
    # current_stage/stage_checkpoints fields the admin panel's
    # stage-progress.tsx already renders for transfermarkt_sync jobs.
    assert [c["stage"] for c in status_body["stage_checkpoints"]] == ["team", "player"]
    assert status_body["current_stage"] == "player"
    assert status_body["all_stages"] == [
        "team",
        "venue",
        "tournament_stage",
        "referee",
        "player",
        "match",
        "match_event",
        "match_team_stat",
        "match_lineup",
        "player_stat",
    ]


@pytest.mark.asyncio
async def test_bulk_upload_rejects_unrecognized_filename_without_dropping_valid_ones(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        "/api/v1/admin/ingestion/bulk-synthetic-upload",
        files=[
            ("files", ("teams.csv", _TEAM_CSV, "text/csv")),
            ("files", ("mystery_export.csv", b"a,b\n1,2\n", "text/csv")),
        ],
    )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["job_id"], int)
    file_results = {f["filename"]: f for f in body["files"]}
    assert file_results["teams.csv"]["accepted"] is True
    assert file_results["teams.csv"]["table_name"] == "team"
    assert file_results["mystery_export.csv"]["accepted"] is False
    assert file_results["mystery_export.csv"]["table_name"] is None
    assert "mystery_export.csv" in file_results["mystery_export.csv"]["reason"]


@pytest.mark.asyncio
async def test_bulk_upload_with_zero_accepted_files_returns_400_and_creates_no_job(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[parse_jwt_data] = _admin_token_data

    response = await client.post(
        "/api/v1/admin/ingestion/bulk-synthetic-upload",
        files=[
            ("files", ("mystery_export.csv", b"a,b\n1,2\n", "text/csv")),
            ("files", ("another_unknown.csv", b"a,b\n1,2\n", "text/csv")),
        ],
    )

    app.dependency_overrides.clear()
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert len(detail["files"]) == 2
    assert all(not f["accepted"] for f in detail["files"])

    async with SessionFactory() as session:
        result = await session.execute(
            text("SELECT count(*) FROM ingestion_job WHERE requested_by_user_id = :id"),
            {"id": _ADMIN_USER_ID},
        )
        assert result.scalar_one() == 0
