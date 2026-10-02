"""The fixture itself: seeding is idempotent and teardown leaves no rows behind."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory
from tests.golden import fixture_career as career
from tests.golden import fixture_data as data
from tests.golden import fixture_matches
from tests.golden.seeding import count_fixture_rows, delete_fixture_rows, seed_fixture_rows

_EXPECTED_ROW_COUNTS = {
    "national_team": len(data.TEAMS),
    "player": len(data.PLAYERS),
    "match": len(fixture_matches.MATCHES),
    "real_player": len(career.REAL_PLAYERS),
}
_NO_ROWS = dict.fromkeys(_EXPECTED_ROW_COUNTS, 0)


async def test_seeding_twice_in_a_row_does_not_duplicate_rows(
    golden_session: AsyncSession,
) -> None:
    await seed_fixture_rows(golden_session)
    await golden_session.commit()

    assert await count_fixture_rows(golden_session) == _EXPECTED_ROW_COUNTS


async def test_delete_removes_every_fixture_row_and_reseeding_restores_them() -> None:
    async with SessionFactory() as session:
        await seed_fixture_rows(session)
        await session.commit()
        try:
            assert await count_fixture_rows(session) == _EXPECTED_ROW_COUNTS
        finally:
            await delete_fixture_rows(session)
            await session.commit()

        assert await count_fixture_rows(session) == _NO_ROWS
