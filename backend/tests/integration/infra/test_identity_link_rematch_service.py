"""Integration test against a real Postgres instance (no mocking of the
parts under test, per AGENTS.md's testing anti-pattern table): proves
`IdentityLinkRematchService.rematch()` actually wipes `player_identity_link`
via the real repository and regenerates it as a clean insert, replacing a
row an admin manually reviewed rather than leaving it untouched.

`player_repository`/`real_player_repository` are fakes here, not because
mocking is preferred (it isn't -- see AGENTS.md), but because the real
roster/Transfermarkt tables in this shared dev database hold production-scale
data (~1.2k roster players x ~50k real players): a full real rematch over
that data takes minutes (verified: ~150s), which is `PlayerIdentityMatchingService`'s
pre-existing O(n*m) cost, unrelated to and out of scope for this feature.
Faking only the two read sources keeps this test fast and deterministic
while still exercising the real `player_identity_link` delete+upsert this
feature actually depends on -- the router itself is covered separately by
`tests/integration/api/admin/test_identity_link_router.py` (job creation,
the confirm gate, and the admin gate), since the real work runs in an async
Arq task the router only enqueues, never runs inline.
"""

from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.services.identity_link_rematch_service import IdentityLinkRematchService
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
)
from src.domain.players.model.player import Player
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.ingestion_job_repository import (
    _SqlAlchemyIngestionJobRepository,
)
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.repositories.player_identity_link_repository import (
    _SqlAlchemyPlayerIdentityLinkRepository,
)

_TEAM_ID = 990501
_PLAYER_ID = 990501
_REAL_PLAYER_ID = 990501
_USER_ID = 990501
_DATE_OF_BIRTH = "2001-03-14"


class _FakePlayerRepository:
    def __init__(self, players: list[Player]) -> None:
        self._players = players

    async def list(self, limit: int = 100, offset: int = 0) -> list[Player]:
        return self._players

    async def get(self, player_id: int):  # pragma: no cover - unused
        raise NotImplementedError


class _FakeRealPlayerRepository:
    def __init__(self, candidates: list[dict]) -> None:
        self._candidates = candidates

    async def list_match_candidates(self) -> list[dict]:
        return self._candidates

    async def get(self, player_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def search(self, query: str, limit: int = 20, offset: int = 0):  # pragma: no cover
        raise NotImplementedError


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, group_letter, "
                "confederation, fifa_ranking_pre_tournament, elo_rating, manager_name) "
                "VALUES (:id, 'Rematch Test Team', 'RMT', 'A', 'UEFA', 1, 1000, 'Coach')"
            ),
            {"id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Rematch Test Player', 'FW', 'Test Club', 1000000, 10, "
                f"'{_DATE_OF_BIRTH}', 180, 5)"
            ),
            {"id": _PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO real_player (player_id, first_name, last_name, date_of_birth, "
                "height_cm, position, profile_url, last_synced_at) "
                f"VALUES (:id, 'Rematch', 'Test Player', '{_DATE_OF_BIRTH}', 180, 'Forward', "
                "'https://example.test/rematch', now())"
            ),
            {"id": _REAL_PLAYER_ID},
        )
        # A separate :name param, not split_part(:email, ...) -- reusing the
        # same bind parameter as both a plain value and a function argument
        # makes asyncpg's extended-protocol type inference raise
        # AmbiguousParameterError ("text versus character varying") on a
        # cold prepare. Verified live and pre-existing elsewhere in this
        # suite, independent of this feature.
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, :name, 'hash', true, now())"
            ),
            {
                "id": _USER_ID,
                "email": "identity-link-rematch-test@example.test",
                "name": "identity-link-rematch-test",
            },
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM player_identity_link WHERE player_id = :id"), {"id": _PLAYER_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM ingestion_job WHERE requested_by_user_id = :id"), {"id": _USER_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM player WHERE player_id = :id"), {"id": _PLAYER_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM real_player WHERE player_id = :id"), {"id": _REAL_PLAYER_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM national_team WHERE team_id = :id"), {"id": _TEAM_ID}
        )
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _USER_ID})
        await cleanup_session.commit()
    await engine.dispose()


async def test_rematch_replaces_a_manually_reviewed_link_with_a_fresh_auto_approved_one(
    db_session: AsyncSession,
) -> None:
    from datetime import date

    identity_link_repository = _SqlAlchemyPlayerIdentityLinkRepository(db_session)
    job_repository = _SqlAlchemyIngestionJobRepository(db_session)

    # Seed a link an admin manually rejected -- a real rematch must not
    # preserve this decision (unlike upsert_candidates' ON CONFLICT alone).
    old_link_id = (
        await db_session.execute(
            text(
                "INSERT INTO player_identity_link "
                "(player_id, real_player_id, match_method, match_confidence, "
                "status, reviewed_by_user_id, reviewed_by_admin) "
                "VALUES (:player_id, :real_player_id, 'MANUAL', NULL, 'REJECTED', :user_id, true) "
                "RETURNING id"
            ),
            {"player_id": _PLAYER_ID, "real_player_id": _REAL_PLAYER_ID, "user_id": _USER_ID},
        )
    ).scalar_one()
    await db_session.commit()

    job = await job_repository.create(
        IngestionJob(
            id=None,
            job_type=IngestionJobType.IDENTITY_LINK_REMATCH,
            status=IngestionJobStatus.QUEUED,
            source_label="test-rematch",
            requested_by_user_id=_USER_ID,
        )
    )
    service = IdentityLinkRematchService(
        identity_link_repository=identity_link_repository,
        player_repository=_FakePlayerRepository(
            [
                Player(
                    id=_PLAYER_ID,
                    team_id=_TEAM_ID,
                    name="Rematch Test Player",
                    position="FW",
                    club_team="Test Club",
                    market_value_eur=1000000,
                    caps=10,
                    date_of_birth=date(2001, 3, 14),
                    height_cm=180,
                    goals=5,
                )
            ]
        ),
        real_player_repository=_FakeRealPlayerRepository(
            [
                {
                    "player_id": _REAL_PLAYER_ID,
                    "first_name": "Rematch",
                    "last_name": "Test Player",
                    "date_of_birth": date(2001, 3, 14),
                    "height_in_cm": 180,
                    "current_national_team_id": None,
                }
            ]
        ),
        ingestion_repository=_SqlAlchemyIngestionRepository(db_session),
        ingestion_job_repository=job_repository,
        matching_service=PlayerIdentityMatchingService(),
    )

    result = await service.rematch(job)

    assert result.status == IngestionJobStatus.SUCCEEDED
    assert result.row_counts == {"player_identity_link": 1}

    # The manually reviewed row is gone -- not stomped in place, deleted.
    assert await identity_link_repository.get(old_link_id) is None

    fresh_link_id = (
        await db_session.execute(
            text("SELECT id FROM player_identity_link WHERE player_id = :id"),
            {"id": _PLAYER_ID},
        )
    ).scalar_one()
    fresh_link = await identity_link_repository.get(fresh_link_id)
    assert fresh_link is not None
    assert fresh_link.id != old_link_id
    assert fresh_link.real_player_id == _REAL_PLAYER_ID
    assert fresh_link.match_confidence == Decimal("1.000")
    # Auto-accepted by the matching pipeline, not an admin decision --
    # reviewed_by_user_id must be None, not the old reviewer's id.
    assert fresh_link.reviewed_by_user_id is None
