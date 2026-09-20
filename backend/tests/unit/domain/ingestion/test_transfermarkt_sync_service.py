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
from src.domain.national_teams.model.national_team import NationalTeam
from src.domain.players.model.player import Player
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.real_organization_schema import RealClubSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSchema

_NATIONAL_TEAM_ROW = {
    "national_team_id": "1",
    "name": "Testland",
    "country_name": "Testland",
    "confederation": "UEFA",
    "fifa_ranking": "10",
    "squad_size": "23",
    "average_age": "27.0",
    "total_market_value": "100000000",
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
        self.requested_tables: list[str] = []

    async def stream_csv_rows(self, table_name: str):
        self.requested_tables.append(table_name)
        for row in self._tables.get(table_name, []):
            yield row


class _FailingClient:
    async def stream_csv_rows(self, table_name: str):
        raise RuntimeError("source unavailable")
        yield  # pragma: no cover - unreachable, makes this an async generator


class _FakeIngestionRepository:
    def __init__(
        self,
        call_order: list[str] | None = None,
        persisted_rows: dict[type, list[dict]] | None = None,
    ) -> None:
        self._call_order = call_order
        self._persisted_rows = persisted_rows or {}
        self.update_matched_calls: list[tuple[type, str, list[dict]]] = []

    async def upsert_many(self, schema_cls, rows, conflict_columns) -> UpsertResult:
        if self._call_order is not None and schema_cls.__tablename__ == "real_player":
            self._call_order.append("real_player")
        return UpsertResult(table_name=schema_cls.__tablename__, row_count=len(rows))

    async def has_rows(self, schema_cls) -> bool:
        return bool(self._persisted_rows.get(schema_cls))

    async def fetch_columns(self, schema_cls, columns) -> list[dict]:
        return [
            {column: row[column] for column in columns}
            for row in self._persisted_rows.get(schema_cls, [])
        ]

    async def has_non_null_column(self, schema_cls, column) -> bool:
        return any(row.get(column) is not None for row in self._persisted_rows.get(schema_cls, []))

    async def update_matched(self, schema_cls, key_column, rows) -> UpsertResult:
        if self._call_order is not None and schema_cls.__tablename__ == "national_team":
            self._call_order.append("national_team")
        self.update_matched_calls.append((schema_cls, key_column, rows))
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


class _FakeNationalTeamRepository:
    def __init__(self, teams: list[NationalTeam]) -> None:
        self._teams = teams

    async def get(self, team_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def list(self, limit: int = 100, offset: int = 0) -> list[NationalTeam]:
        return self._teams


class _FakePlayerRepository:
    def __init__(self, players: list[Player]) -> None:
        self._players = players

    async def get(self, player_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def list(self, limit: int = 100, offset: int = 0) -> list[Player]:
        return self._players


class _FakeIdentityLinkRepository:
    def __init__(self, call_order: list[str] | None = None) -> None:
        self.upserted_candidates = []
        self._call_order = call_order

    async def list_pending(self, limit: int = 100, offset: int = 0):  # pragma: no cover
        raise NotImplementedError

    async def get(self, link_id: int):  # pragma: no cover - unused
        raise NotImplementedError

    async def update_status(self, link_id, status, reviewed_by_user_id):  # pragma: no cover
        raise NotImplementedError

    async def upsert_candidates(self, candidates):
        self.upserted_candidates = candidates
        if self._call_order is not None:
            self._call_order.append("player_identity_link")
        return UpsertResult(table_name="player_identity_link", row_count=len(candidates))


class _FakeDetailSync:
    def __init__(self) -> None:
        self.player_scoped_calls: list[set[int]] = []

    async def sync_player_scoped_tables(
        self,
        matched_real_player_ids: set[int],
        known_club_ids: set[str],
        skip_populated: bool = False,
    ) -> dict[str, int]:
        self.player_scoped_calls.append(matched_real_player_ids)
        return {"player_valuations": 0, "transfers": 0}

    async def sync_match_data(
        self,
        matched_real_player_ids,
        matched_real_club_ids,
        known_club_ids,
        skip_populated: bool = False,
    ) -> dict[str, int]:
        return {"game_lineups": 0, "game_events": 0, "club_games": 0}

    async def sync_season_stats(
        self, matched_real_player_ids: set[int], skip_populated: bool = False
    ) -> int:
        return 0


def _build_service(
    client,
    job_repository,
    national_team_repository,
    player_repository,
    detail_sync,
    identity_link_repository=None,
    ingestion_repository=None,
):
    return TransfermarktSyncService(
        transfermarkt_client=client,
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=ingestion_repository or _FakeIngestionRepository(),
        ingestion_job_repository=job_repository,
        national_team_repository=national_team_repository,
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
    national_team_repository = _FakeNationalTeamRepository(
        [NationalTeam(1, "Testland", "TST", "A", "UEFA", 10, 1800, "Coach")]
    )
    player_repository = _FakePlayerRepository(
        [Player(1, 1, "John Doe", "FWD", "Some FC", 20000000, 30, date(1998, 5, 10), 182, 10)]
    )
    identity_link_repository = _FakeIdentityLinkRepository()
    detail_sync = _FakeDetailSync()
    service = _build_service(
        client,
        job_repository,
        national_team_repository,
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
async def test_run_sync_persists_real_player_before_identity_link():
    # player_identity_link.real_player_id has a foreign key into real_player.
    # Upserting identity-link candidates before the matched real_player rows
    # exist raises ForeignKeyViolationError (found live, immediately after
    # fixing the real_player_id collision above -- both bugs were hit in the
    # same pipeline run).
    call_order: list[str] = []
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
            ],
        }
    )
    job_repository = _FakeJobRepository(_job())
    national_team_repository = _FakeNationalTeamRepository(
        [NationalTeam(1, "Testland", "TST", "A", "UEFA", 10, 1800, "Coach")]
    )
    player_repository = _FakePlayerRepository(
        [Player(1, 1, "John Doe", "FWD", "Some FC", 20000000, 30, date(1998, 5, 10), 182, 10)]
    )
    service = _build_service(
        client,
        job_repository,
        national_team_repository,
        player_repository,
        _FakeDetailSync(),
        identity_link_repository=_FakeIdentityLinkRepository(call_order),
        ingestion_repository=_FakeIngestionRepository(call_order),
    )

    await service.run_sync(_job())

    assert call_order == ["national_team", "real_player", "player_identity_link"]


@pytest.mark.asyncio
async def test_run_sync_reraises_original_error_leaving_job_running():
    # run_sync does NOT mark the job failed itself: a failure originating
    # from a DB statement leaves the session's transaction aborted, and this
    # service has no session access to roll back before writing. Marking
    # failed is the caller's job (infra/task_queue/tasks.py's _fail_job),
    # which does hold the session and rolls back first. See that module's
    # docstring for the real-world bug this shape avoids.
    job_repository = _FakeJobRepository(_job())
    service = _build_service(
        _FailingClient(),
        job_repository,
        _FakeNationalTeamRepository([]),
        _FakePlayerRepository([]),
        _FakeDetailSync(),
    )

    with pytest.raises(RuntimeError):
        await service.run_sync(_job())

    assert job_repository.updates[-1].status == IngestionJobStatus.RUNNING


@pytest.mark.asyncio
async def test_run_sync_with_skip_populated_derives_scope_from_db_without_refetching():
    # Every table this pipeline can populate already has rows: national_teams,
    # clubs, and players must all be skipped, and the scope detail_sync needs
    # (matched_real_player_ids/known_club_ids) must come from the DB, not
    # from re-fetching and re-matching the source CSVs.
    client = _FakeTransfermarktClient(
        {
            "national_teams": [_NATIONAL_TEAM_ROW],
            "clubs": [{"club_id": "77", "name": "Some FC"}],
            "players": [
                _player_row(
                    player_id="500",
                    first_name="John",
                    last_name="Doe",
                    date_of_birth="1998-05-10",
                    current_club_id="77",
                ),
            ],
        }
    )
    job_repository = _FakeJobRepository(_job())
    national_team_repository = _FakeNationalTeamRepository(
        [NationalTeam(1, "Testland", "TST", "A", "UEFA", 10, 1800, "Coach")]
    )
    player_repository = _FakePlayerRepository(
        [Player(1, 1, "John Doe", "FWD", "Some FC", 20000000, 30, date(1998, 5, 10), 182, 10)]
    )
    ingestion_repository = _FakeIngestionRepository(
        persisted_rows={
            NationalTeamSchema: [{"team_id": 1, "real_national_team_id": 1}],
            RealClubSchema: [{"club_id": "77"}],
            RealPlayerSchema: [{"player_id": 500, "current_club_id": "77"}],
        }
    )
    detail_sync = _FakeDetailSync()
    service = _build_service(
        client,
        job_repository,
        national_team_repository,
        player_repository,
        detail_sync,
        ingestion_repository=ingestion_repository,
    )

    result = await service.run_sync(_job(), skip_populated=True)

    assert result.status == IngestionJobStatus.SUCCEEDED
    assert client.requested_tables == []
    assert result.row_counts["national_teams"] == 0
    assert result.row_counts["clubs"] == 0
    assert result.row_counts["players"] == 0
    assert detail_sync.player_scoped_calls == [{500}]


@pytest.mark.asyncio
async def test_national_teams_step_only_updates_matched_wc2026_teams():
    # national_team's base rows come only from the synthetic WC2026 upload
    # -- this step must never create a row for a Transfermarkt country with
    # no WC2026 match (e.g. "Unmatchedland" below), only UPDATE the
    # enrichment columns of a row that already exists and matched by name.
    client = _FakeTransfermarktClient(
        {
            "national_teams": [
                _NATIONAL_TEAM_ROW,
                {
                    "national_team_id": "2",
                    "name": "Unmatchedland",
                    "country_name": "Unmatchedland",
                    "confederation": "CONMEBOL",
                    "fifa_ranking": "50",
                    "squad_size": "22",
                    "average_age": "25.0",
                    "total_market_value": "5000000",
                    "coach_name": "Someone Else",
                    "url": "https://example.com/other",
                },
            ],
            "clubs": [],
            "players": [],
        }
    )
    job_repository = _FakeJobRepository(_job())
    national_team_repository = _FakeNationalTeamRepository(
        [NationalTeam(1, "Testland", "TST", "A", "UEFA", 10, 1800, "Coach")]
    )
    ingestion_repository = _FakeIngestionRepository()
    service = _build_service(
        client,
        job_repository,
        national_team_repository,
        _FakePlayerRepository([]),
        _FakeDetailSync(),
        ingestion_repository=ingestion_repository,
    )

    result = await service.run_sync(_job())

    assert result.row_counts["national_teams"] == 1
    assert len(ingestion_repository.update_matched_calls) == 1
    schema_cls, key_column, rows = ingestion_repository.update_matched_calls[0]
    assert schema_cls is NationalTeamSchema
    assert key_column == "team_id"
    assert rows == [
        {
            "team_id": 1,
            "real_national_team_id": 1,
            "squad_size": 23,
            "average_age": 27.0,
            "total_market_value_eur": 100000000,
            "url": "https://example.com",
        }
    ]
