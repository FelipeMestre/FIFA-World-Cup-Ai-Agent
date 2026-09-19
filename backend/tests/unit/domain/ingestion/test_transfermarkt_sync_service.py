from datetime import date

import pytest

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
)
from src.domain.ingestion.services.roster_scoping_service import RosterScopingService
from src.domain.ingestion.services.transfermarkt_sync_service import TransfermarktSyncService
from src.domain.players.model.player import Player
from src.domain.teams.model.team import Team
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult

_NATIONAL_TEAM_ROW = {
    "national_team_id": "1",
    "name": "Testland",
    "country_name": "Testland",
    "confederation": "UEFA",
    "fifa_ranking": "10",
    "squad_size": "23",
    "average_age": "27.0",
    "total_market_value_eur": "100000000",
    "coach_name": "Coach",
    "url": "https://example.com",
}
_BASE_PLAYER_ROW = {
    "country_of_birth": "Nowhere",
    "country_of_citizenship": "Nowhere",
    "position": "Defender",
    "sub_position": "Centre-Back",
    "foot": "left",
    "height_in_cm": "185",
    "contract_expiration_date": "",
    "market_value_in_eur": "1000000",
    "highest_market_value_in_eur": "1000000",
    "url": "https://example.com/player",
}


def _player_row(**overrides) -> dict[str, str]:
    return {**_BASE_PLAYER_ROW, **overrides}


def _job() -> IngestionJob:
    return IngestionJob(
        id=1,
        job_type=IngestionJobType.TRANSFERMARKT_SYNC,
        status=IngestionJobStatus.QUEUED,
        source_label="full-sync",
        requested_by_user_id=1,
    )


class _FakeTransfermarktClient:
    def __init__(self, tables: dict[str, list[dict[str, str]]]) -> None:
        self._tables = tables

    async def stream_csv_rows(self, table_name: str):
        for row in self._tables.get(table_name, []):
            yield row


class _FailingClient:
    async def stream_csv_rows(self, table_name: str):
        raise RuntimeError("source unavailable")
        yield  # pragma: no cover - unreachable, makes this an async generator


class _FakeIngestionRepository:
    async def upsert_many(self, schema_cls, rows, conflict_columns) -> UpsertResult:
        return UpsertResult(table_name=schema_cls.__tablename__, row_count=len(rows))


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


class _FakeTeamRepository:
    def __init__(self, teams: list[Team]) -> None:
        self._teams = teams

    async def get(self, team_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def list(self, limit: int = 100, offset: int = 0) -> list[Team]:
        return self._teams


class _FakePlayerRepository:
    def __init__(self, players: list[Player]) -> None:
        self._players = players

    async def get(self, player_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def list(self, limit: int = 100, offset: int = 0) -> list[Player]:
        return self._players


class _FakeIdentityLinkRepository:
    def __init__(self) -> None:
        self.upserted_candidates = []

    async def list_pending(self, limit: int = 100, offset: int = 0):  # pragma: no cover
        raise NotImplementedError

    async def get(self, link_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def update_status(self, link_id, status, reviewed_by_user_id):  # pragma: no cover
        raise NotImplementedError

    async def upsert_candidates(self, candidates):
        self.upserted_candidates = candidates
        return UpsertResult(table_name="player_identity_link", row_count=len(candidates))


class _FakeDetailSync:
    def __init__(self) -> None:
        self.player_scoped_calls: list[set[int]] = []

    async def sync_player_scoped_tables(self, matched_real_player_ids: set[int]) -> dict[str, int]:
        self.player_scoped_calls.append(matched_real_player_ids)
        return {"player_valuations": 0, "transfers": 0}

    async def sync_match_data(
        self, matched_real_player_ids, matched_real_club_ids
    ) -> dict[str, int]:
        return {"game_lineups": 0, "game_events": 0, "club_games": 0}

    async def sync_season_stats(self, matched_real_player_ids: set[int]) -> int:
        return 0


def _build_service(
    client,
    job_repository,
    team_repository,
    player_repository,
    detail_sync,
    identity_link_repository=None,
):
    return TransfermarktSyncService(
        transfermarkt_client=client,
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=_FakeIngestionRepository(),
        ingestion_job_repository=job_repository,
        team_repository=team_repository,
        player_repository=player_repository,
        identity_link_repository=identity_link_repository or _FakeIdentityLinkRepository(),
        roster_scoping_service=RosterScopingService(),
        matching_service=PlayerIdentityMatchingService(),
        detail_sync=detail_sync,
    )


@pytest.mark.asyncio
async def test_run_sync_persists_only_matched_players_and_succeeds_job():
    client = _FakeTransfermarktClient(
        {
            "national_teams": [_NATIONAL_TEAM_ROW],
            "clubs": [],
            "players": [
                _player_row(
                    player_id="500",
                    first_name="John",
                    last_name="Doe",
                    date_of_birth="1998-05-10",
                    current_club_id="77",
                ),
                _player_row(
                    player_id="999",
                    first_name="Unrelated",
                    last_name="Nobody",
                    date_of_birth="1990-01-01",
                    current_club_id="88",
                ),
            ],
        }
    )
    job_repository = _FakeJobRepository(_job())
    team_repository = _FakeTeamRepository(
        [Team(1, "Testland", "TST", "A", "UEFA", 10, 1800, "Coach")]
    )
    player_repository = _FakePlayerRepository(
        [Player(1, 1, "John Doe", "FWD", "Some FC", 20000000, 30, date(1998, 5, 10), 182, 10)]
    )
    identity_link_repository = _FakeIdentityLinkRepository()
    detail_sync = _FakeDetailSync()
    service = _build_service(
        client,
        job_repository,
        team_repository,
        player_repository,
        detail_sync,
        identity_link_repository,
    )

    result = await service.run_sync(_job())

    assert result.status == IngestionJobStatus.SUCCEEDED
    assert len(identity_link_repository.upserted_candidates) == 1
    assert identity_link_repository.upserted_candidates[0].real_player_id == 500
    # Only the matched player (500) is persisted, not the unrelated one (999).
    assert detail_sync.player_scoped_calls == [{500}]
    assert result.row_counts["players"] == 1


@pytest.mark.asyncio
async def test_run_sync_marks_job_failed_on_source_error():
    job_repository = _FakeJobRepository(_job())
    service = _build_service(
        _FailingClient(),
        job_repository,
        _FakeTeamRepository([]),
        _FakePlayerRepository([]),
        _FakeDetailSync(),
    )

    with pytest.raises(RuntimeError):
        await service.run_sync(_job())

    assert job_repository.updates[-1].status == IngestionJobStatus.FAILED
