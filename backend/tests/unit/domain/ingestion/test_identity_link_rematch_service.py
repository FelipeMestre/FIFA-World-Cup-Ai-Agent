"""TDD unit tests for `IdentityLinkRematchService`: fake repositories, no DB.
Asserts the delete-then-regenerate ordering (the whole point of this service
over reusing `upsert_candidates` alone -- see the feature's own task file)
and the national_team_id_by_team_id derivation mirrored from
`TransfermarktSyncService`'s resume-mode precedent.
"""

from datetime import date

import pytest

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import PlayerMatchMethod
from src.domain.ingestion.services.identity_link_rematch_service import IdentityLinkRematchService
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
)
from src.domain.players.model.player import Player
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema


def _job() -> IngestionJob:
    return IngestionJob(
        id=1,
        job_type=IngestionJobType.IDENTITY_LINK_REMATCH,
        status=IngestionJobStatus.QUEUED,
        source_label="admin-triggered-rematch",
        requested_by_user_id=1,
    )


class _FakeIdentityLinkRepository:
    def __init__(self, call_order: list[str] | None = None) -> None:
        self._call_order = call_order
        self.delete_all_called = False
        self.upserted_candidates: list[PlayerIdentityCandidate] = []

    async def delete_all(self) -> int:
        self.delete_all_called = True
        if self._call_order is not None:
            self._call_order.append("delete_all")
        return 3

    async def upsert_candidates(self, candidates: list[PlayerIdentityCandidate]) -> UpsertResult:
        self.upserted_candidates = candidates
        if self._call_order is not None:
            self._call_order.append("upsert_candidates")
        return UpsertResult(table_name="player_identity_link", row_count=len(candidates))

    # Unused by this service, but present on the real interface.
    async def list_by_status(self, status, limit: int = 100, offset: int = 0):  # pragma: no cover
        raise NotImplementedError

    async def count_by_status(self, status):  # pragma: no cover - unused
        raise NotImplementedError

    async def get(self, link_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def update_status(self, link_id, status, reviewed_by_user_id):  # pragma: no cover
        raise NotImplementedError

    async def reassign(self, link_id, new_real_player_id, admin_user_id):  # pragma: no cover
        raise NotImplementedError


class _FakePlayerRepository:
    def __init__(self, players: list[Player], call_order: list[str] | None = None) -> None:
        self._players = players
        self._call_order = call_order

    async def list(self, limit: int = 100, offset: int = 0) -> list[Player]:
        if self._call_order is not None:
            self._call_order.append("list_players")
        return self._players

    async def get(self, player_id: int):  # pragma: no cover - unused
        raise NotImplementedError


class _FakeRealPlayerRepository:
    def __init__(self, candidates: list[dict], call_order: list[str] | None = None) -> None:
        self._candidates = candidates
        self._call_order = call_order

    async def list_match_candidates(self) -> list[dict]:
        if self._call_order is not None:
            self._call_order.append("list_candidates")
        return self._candidates

    async def get(self, player_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def search(self, query: str, limit: int = 20, offset: int = 0):  # pragma: no cover
        raise NotImplementedError


class _FakeIngestionRepository:
    def __init__(self, national_team_rows: list[dict]) -> None:
        self._national_team_rows = national_team_rows

    async def fetch_columns(self, schema_cls, columns) -> list[dict]:
        assert schema_cls is NationalTeamSchema
        return [{column: row[column] for column in columns} for row in self._national_team_rows]

    async def upsert_many(self, schema_cls, rows, conflict_columns):  # pragma: no cover - unused
        raise NotImplementedError

    async def has_rows(self, schema_cls) -> bool:  # pragma: no cover - unused
        raise NotImplementedError

    async def has_non_null_column(self, schema_cls, column) -> bool:  # pragma: no cover
        raise NotImplementedError

    async def update_matched(self, schema_cls, key_column, rows):  # pragma: no cover - unused
        raise NotImplementedError


class _FakeJobRepository:
    def __init__(self, job: IngestionJob) -> None:
        self._job = job
        self.updates: list[IngestionJob] = []

    async def create(self, job: IngestionJob) -> IngestionJob:  # pragma: no cover - unused
        raise NotImplementedError

    async def get(self, job_id: int) -> IngestionJob | None:
        return self._job

    async def update(self, job: IngestionJob) -> IngestionJob:
        self.updates.append(job)
        self._job = job
        return job


class _SpyMatchingService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def match(self, synthetic_players, real_player_candidates, national_team_id_by_team_id):
        self.calls.append((synthetic_players, real_player_candidates, national_team_id_by_team_id))
        return []


def _build_service(
    identity_link_repository=None,
    player_repository=None,
    real_player_repository=None,
    ingestion_repository=None,
    job_repository=None,
    matching_service=None,
):
    return IdentityLinkRematchService(
        identity_link_repository=identity_link_repository or _FakeIdentityLinkRepository(),
        player_repository=player_repository or _FakePlayerRepository([]),
        real_player_repository=real_player_repository or _FakeRealPlayerRepository([]),
        ingestion_repository=ingestion_repository or _FakeIngestionRepository([]),
        ingestion_job_repository=job_repository or _FakeJobRepository(_job()),
        matching_service=matching_service or PlayerIdentityMatchingService(),
    )


@pytest.mark.asyncio
async def test_rematch_deletes_before_fetching_and_regenerating():
    call_order: list[str] = []
    identity_link_repository = _FakeIdentityLinkRepository(call_order)
    player_repository = _FakePlayerRepository(
        [Player(1, 1, "John Doe", "FWD", "Some FC", 1000000, 10, date(1998, 5, 10), 182, 5)],
        call_order,
    )
    real_player_repository = _FakeRealPlayerRepository(
        [
            {
                "player_id": 500,
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": date(1998, 5, 10),
                "height_in_cm": 182,
                "current_national_team_id": None,
            }
        ],
        call_order,
    )
    service = _build_service(
        identity_link_repository=identity_link_repository,
        player_repository=player_repository,
        real_player_repository=real_player_repository,
    )

    result = await service.rematch(_job())

    assert call_order == ["delete_all", "list_players", "list_candidates", "upsert_candidates"]
    assert result.status == IngestionJobStatus.SUCCEEDED
    assert identity_link_repository.delete_all_called is True


@pytest.mark.asyncio
async def test_rematch_marks_job_running_then_succeeded_with_row_count():
    identity_link_repository = _FakeIdentityLinkRepository()
    player_repository = _FakePlayerRepository(
        [Player(1, 1, "John Doe", "FWD", "Some FC", 1000000, 10, date(1998, 5, 10), 182, 5)]
    )
    real_player_repository = _FakeRealPlayerRepository(
        [
            {
                "player_id": 500,
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": date(1998, 5, 10),
                "height_in_cm": 182,
                "current_national_team_id": None,
            }
        ]
    )
    job_repository = _FakeJobRepository(_job())
    service = _build_service(
        identity_link_repository=identity_link_repository,
        player_repository=player_repository,
        real_player_repository=real_player_repository,
        job_repository=job_repository,
    )

    result = await service.rematch(_job())

    assert [job.status for job in job_repository.updates] == [
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.SUCCEEDED,
    ]
    assert result.row_counts == {"player_identity_link": 1}
    assert len(identity_link_repository.upserted_candidates) == 1
    persisted_candidate = identity_link_repository.upserted_candidates[0]
    assert persisted_candidate.match_method == PlayerMatchMethod.EXACT_NAME_DOB


@pytest.mark.asyncio
async def test_rematch_derives_national_team_id_by_team_id_from_non_null_transfermarkt_ids():
    # Mirrors TransfermarktSyncService's own resume-mode precedent: only rows
    # with a non-null transfermarkt_id contribute to the mapping.
    matching_service = _SpyMatchingService()
    ingestion_repository = _FakeIngestionRepository(
        [
            {"team_id": 1, "transfermarkt_id": 100},
            {"team_id": 2, "transfermarkt_id": None},
        ]
    )
    service = _build_service(
        ingestion_repository=ingestion_repository, matching_service=matching_service
    )

    await service.rematch(_job())

    assert len(matching_service.calls) == 1
    _, _, national_team_id_by_team_id = matching_service.calls[0]
    assert national_team_id_by_team_id == {1: 100}


@pytest.mark.asyncio
async def test_rematch_reraises_original_error_leaving_job_running():
    # Same shape as TransfermarktSyncService.run_sync: this service has no
    # session access to roll back a failed DB statement, so on failure it
    # must re-raise unchanged and let the caller (which holds the session)
    # roll back and persist the failure -- never mask the real error.
    class _FailingIdentityLinkRepository(_FakeIdentityLinkRepository):
        async def delete_all(self) -> int:
            raise RuntimeError("boom")

    job_repository = _FakeJobRepository(_job())
    service = _build_service(
        identity_link_repository=_FailingIdentityLinkRepository(), job_repository=job_repository
    )

    with pytest.raises(RuntimeError, match="boom"):
        await service.rematch(_job())

    assert job_repository.updates[-1].status == IngestionJobStatus.RUNNING
