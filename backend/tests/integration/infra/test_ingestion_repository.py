"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies the generic
`IngestionRepositoryInterface.upsert_many` implementation's actual
`ON CONFLICT DO UPDATE` SQL, and the migration's upgrade/downgrade
roundtrip.

Targets `RealClubSchema` (`real_club`) as the upsert-under-test table since
it has no FK dependencies, keeping the test self-contained.
"""

import subprocess
import sys
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.schemas.real_organization_schema import RealClubSchema

_CLUB_IDS = (990001, 990002)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    # `engine`'s asyncpg connections are bound to the event loop that opened
    # them; pytest-asyncio gives each test function its own loop, so the
    # pool must be disposed on entry/exit or a later test reuses a
    # connection tied to an already-closed loop.
    async with SessionFactory() as session:
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM real_club WHERE club_id = ANY(:ids)"), {"ids": list(_CLUB_IDS)}
        )
        await cleanup_session.commit()
    await engine.dispose()


def _club_row(club_id: int, name: str) -> dict:
    return {
        "club_id": club_id,
        "club_code": f"club-{club_id}",
        "name": name,
        "domestic_competition_id": None,
        "total_market_value_eur": None,
        "squad_size": None,
        "average_age": None,
        "stadium_seats": None,
        "stadium_name": None,
        "coach_name": None,
        "url": f"https://example.test/{club_id}",
    }


@pytest.mark.asyncio
async def test_upsert_many_inserts_new_rows(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionRepository(db_session)
    rows = [_club_row(club_id, "First Name") for club_id in _CLUB_IDS]

    result = await repository.upsert_many(RealClubSchema, rows, conflict_columns=("club_id",))

    assert result.row_count == 2
    assert result.table_name == "real_club"
    persisted = await db_session.get(RealClubSchema, _CLUB_IDS[0])
    assert persisted is not None
    assert persisted.name == "First Name"


@pytest.mark.asyncio
async def test_upsert_many_updates_on_conflict_without_duplicating(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyIngestionRepository(db_session)
    initial_rows = [_club_row(club_id, "Original Name") for club_id in _CLUB_IDS]
    await repository.upsert_many(RealClubSchema, initial_rows, conflict_columns=("club_id",))

    updated_rows = [_club_row(club_id, "Updated Name") for club_id in _CLUB_IDS]
    result = await repository.upsert_many(
        RealClubSchema, updated_rows, conflict_columns=("club_id",)
    )

    assert result.row_count == 2
    count_result = await db_session.execute(
        text("SELECT count(*) FROM real_club WHERE club_id = ANY(:ids)"),
        {"ids": list(_CLUB_IDS)},
    )
    assert count_result.scalar_one() == 2
    updated = await db_session.get(RealClubSchema, _CLUB_IDS[0])
    assert updated is not None
    assert updated.name == "Updated Name"


@pytest.mark.asyncio
async def test_upsert_many_with_no_rows_is_a_noop(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionRepository(db_session)

    result = await repository.upsert_many(RealClubSchema, [], conflict_columns=("club_id",))

    assert result.row_count == 0


@pytest.mark.asyncio
async def test_has_rows_reflects_actual_table_state(db_session: AsyncSession) -> None:
    # Backs the Transfermarkt sync's resume mode: a populated table means
    # the corresponding step can be skipped.
    repository = _SqlAlchemyIngestionRepository(db_session)
    assert await repository.has_rows(RealClubSchema) is False

    await repository.upsert_many(
        RealClubSchema, [_club_row(_CLUB_IDS[0], "Some Club")], conflict_columns=("club_id",)
    )

    assert await repository.has_rows(RealClubSchema) is True


@pytest.mark.asyncio
async def test_fetch_columns_reads_back_requested_columns_only(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionRepository(db_session)
    await repository.upsert_many(
        RealClubSchema,
        [_club_row(club_id, f"Club {club_id}") for club_id in _CLUB_IDS],
        conflict_columns=("club_id",),
    )

    rows = await repository.fetch_columns(RealClubSchema, ["club_id", "name"])

    assert {row["club_id"] for row in rows} == set(_CLUB_IDS)
    assert all(set(row.keys()) == {"club_id", "name"} for row in rows)


async def _table_names() -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names()))


def _run_alembic(*args: str) -> None:
    # Run as a subprocess, not via `alembic.command` in-process: `env.py`
    # calls `asyncio.run(...)`, which cannot execute inside the already
    # running event loop pytest-asyncio provides for this test.
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
async def test_migration_roundtrip() -> None:
    """`alembic upgrade head` / `downgrade db800dd3ee39` roundtrip for the
    migration adding `real_game_lineup`, `real_match_event`,
    `real_club_game`, `ingestion_job`, and `player_identity_link.status`.

    Assumes the DB starts at `head` (the normal state between test runs);
    downgrades to the revision immediately before this migration (targeted
    by explicit revision id, not a relative `-1` hop, so this test stays
    correct regardless of how many migrations now sit on top of this one),
    asserts the new tables are gone, then upgrades back to `head` and
    asserts they exist again.
    """
    new_tables = {"real_game_lineup", "real_match_event", "real_club_game", "ingestion_job"}

    tables_before = await _table_names()
    assert new_tables.issubset(tables_before), (
        "expected the DB to start at head with the PR 1 migration applied"
    )
    await engine.dispose()

    _run_alembic("downgrade", "db800dd3ee39")
    tables_after_downgrade = await _table_names()
    assert new_tables.isdisjoint(tables_after_downgrade)
    await engine.dispose()

    _run_alembic("upgrade", "head")
    tables_after_upgrade = await _table_names()
    assert new_tables.issubset(tables_after_upgrade)
    await engine.dispose()
