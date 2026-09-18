"""Integration tests against a real Postgres instance (no mocking): verifies
the `2026-09-20_add_transfermarkt_detail_upsert_constraints` migration's
upgrade/downgrade roundtrip, and that the generic upsert repository's
`ON CONFLICT` now actually resolves against `real_player_valuation`'s and
`real_transfer`'s `(real_player_id, valuation_date|transfer_date)` unique
constraints -- the gap flagged in PR 3's exit criteria (task 4.3.5).
"""

import subprocess
import sys
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.schemas.real_player_schema import (
    RealPlayerSchema,
    RealPlayerValuationSchema,
    RealTransferSchema,
)

_PLAYER_ID = 990101


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            RealPlayerSchema.__table__.insert().values(
                player_id=_PLAYER_ID,
                first_name="Test",
                last_name="Player",
                position="Midfield",
                profile_url="https://example.test/player",
                last_synced_at=date(2026, 1, 1),
            )
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM real_player_valuation WHERE real_player_id = :id"),
            {"id": _PLAYER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM real_transfer WHERE real_player_id = :id"), {"id": _PLAYER_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM real_player WHERE player_id = :id"), {"id": _PLAYER_ID}
        )
        await cleanup_session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_many_resolves_on_conflict_for_player_valuation(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyIngestionRepository(db_session)
    row = {
        "real_player_id": _PLAYER_ID,
        "valuation_date": date(2026, 1, 15),
        "market_value_eur": 1_000_000,
        "club_name_at_time": "Original Club",
    }

    await repository.upsert_many(
        RealPlayerValuationSchema, [row], conflict_columns=("real_player_id", "valuation_date")
    )
    updated_row = {**row, "market_value_eur": 2_000_000, "club_name_at_time": "New Club"}
    await repository.upsert_many(
        RealPlayerValuationSchema,
        [updated_row],
        conflict_columns=("real_player_id", "valuation_date"),
    )

    count_result = await db_session.execute(
        text("SELECT count(*) FROM real_player_valuation WHERE real_player_id = :id"),
        {"id": _PLAYER_ID},
    )
    assert count_result.scalar_one() == 1
    value_result = await db_session.execute(
        text("SELECT market_value_eur FROM real_player_valuation WHERE real_player_id = :id"),
        {"id": _PLAYER_ID},
    )
    assert value_result.scalar_one() == 2_000_000


@pytest.mark.asyncio
async def test_upsert_many_resolves_on_conflict_for_transfer(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionRepository(db_session)
    row = {
        "real_player_id": _PLAYER_ID,
        "transfer_date": date(2026, 6, 1),
        "transfer_season": "25/26",
        "from_club_name": "Old Club",
        "to_club_name": "New Club",
    }

    await repository.upsert_many(
        RealTransferSchema, [row], conflict_columns=("real_player_id", "transfer_date")
    )
    updated_row = {**row, "to_club_name": "Updated Club"}
    await repository.upsert_many(
        RealTransferSchema, [updated_row], conflict_columns=("real_player_id", "transfer_date")
    )

    count_result = await db_session.execute(
        text("SELECT count(*) FROM real_transfer WHERE real_player_id = :id"), {"id": _PLAYER_ID}
    )
    assert count_result.scalar_one() == 1


async def _constraint_names(table_name: str) -> set[str]:
    async with engine.connect() as conn:
        return set(
            await conn.run_sync(
                lambda sync_conn: {
                    c["name"] for c in inspect(sync_conn).get_unique_constraints(table_name)
                }
            )
        )


def _run_alembic(*args: str) -> None:
    # Subprocess, not `alembic.command` in-process: `env.py` calls
    # `asyncio.run(...)`, which cannot run inside pytest-asyncio's already
    # running event loop.
    subprocess.run(
        [sys.executable, "-m", "alembic", *args], check=True, capture_output=True, text=True
    )


@pytest.mark.asyncio
async def test_migration_roundtrip() -> None:
    """`alembic upgrade head` / `downgrade -1` roundtrip for the migration
    adding the `real_player_valuation`/`real_transfer` natural-key unique
    constraints.
    """
    valuation_constraints_before = await _constraint_names("real_player_valuation")
    transfer_constraints_before = await _constraint_names("real_transfer")
    assert "real_player_valuation_real_player_id_key" in valuation_constraints_before
    assert "real_transfer_real_player_id_key" in transfer_constraints_before
    await engine.dispose()

    _run_alembic("downgrade", "-1")
    valuation_constraints_after_downgrade = await _constraint_names("real_player_valuation")
    transfer_constraints_after_downgrade = await _constraint_names("real_transfer")
    assert "real_player_valuation_real_player_id_key" not in valuation_constraints_after_downgrade
    assert "real_transfer_real_player_id_key" not in transfer_constraints_after_downgrade
    await engine.dispose()

    _run_alembic("upgrade", "head")
    valuation_constraints_after_upgrade = await _constraint_names("real_player_valuation")
    transfer_constraints_after_upgrade = await _constraint_names("real_transfer")
    assert "real_player_valuation_real_player_id_key" in valuation_constraints_after_upgrade
    assert "real_transfer_real_player_id_key" in transfer_constraints_after_upgrade
    await engine.dispose()
