"""Pytest fixtures for the golden set: seeded database and the real tool registry.

The seed is function-scoped on purpose. The root `tests/conftest.py` disposes the shared
engine after every test because pytest-asyncio gives each test its own event loop; a
module-scoped seed would keep pooled connections alive across loops. The dataset is
small (about 100 rows), so reseeding per test costs milliseconds.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.tools.registry import ToolDefinition, build_tool_registry
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.match_analytics_repository import (
    get_match_analytics_repository,
)
from src.infra.postgres.repositories.player_analytics_repository import (
    get_player_analytics_repository,
)
from src.infra.postgres.repositories.team_analytics_repository import (
    get_team_analytics_repository,
)
from tests.golden.seeding import delete_fixture_rows, seed_fixture_rows


@pytest.fixture
async def golden_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await seed_fixture_rows(session)
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await delete_fixture_rows(cleanup_session)
        await cleanup_session.commit()
    await engine.dispose()


@pytest.fixture
def registry(golden_session: AsyncSession) -> dict[str, ToolDefinition]:
    """The production tool registry, bound to real repositories on the seeded session."""
    return build_tool_registry(
        team_analytics_repository=get_team_analytics_repository(golden_session),
        player_analytics_repository=get_player_analytics_repository(golden_session),
        match_analytics_repository=get_match_analytics_repository(golden_session),
    )
