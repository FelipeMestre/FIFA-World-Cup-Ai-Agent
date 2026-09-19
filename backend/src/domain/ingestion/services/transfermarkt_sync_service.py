"""Top-level Transfermarkt sync orchestrator: reference ingest -> team-level
scoping -> identity matching -> detail pulls (delegated to
`TransfermarktDetailSync`), updating the `IngestionJob` throughout.

Correction (verified against the live source): `players.csv` DOES carry
`current_national_team_id` -- an earlier revision of this module assumed
otherwise without checking the real export. This still buffers `players.csv`
in full and matches against every candidate rather than pre-filtering by
that column; it remains correct (only matched `player_id`s get persisted),
just not the most efficient shape. Pre-filtering by
`current_national_team_id` before matching is a valid follow-up
optimization, not a correctness fix.
"""

from collections.abc import AsyncIterator
from typing import Any

from src.domain.ingestion.model.ingestion_job import IngestionJob
from src.domain.ingestion.services import csv_parsers as parsers
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
)
from src.domain.ingestion.services.roster_scoping_service import RosterScopingService
from src.domain.ingestion.services.transfermarkt_detail_specs import TRANSFERMARKT_DETAIL_SPECS
from src.domain.ingestion.services.transfermarkt_detail_sync import TransfermarktDetailSync
from src.domain.ingestion.services.transfermarkt_reference_specs import (
    TRANSFERMARKT_REFERENCE_SPECS,
)
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
)
from src.infra.postgres.interfaces.player_identity_link_repository_interface import (
    PlayerIdentityLinkRepositoryInterface,
)
from src.infra.postgres.interfaces.player_repository_interface import PlayerRepositoryInterface
from src.infra.postgres.interfaces.team_repository_interface import TeamRepositoryInterface
from src.infra.transfermarkt.client_interface import TransfermarktClientInterface

_REFERENCE_SPECS_BY_NAME = {spec.source_name: spec for spec in TRANSFERMARKT_REFERENCE_SPECS}
_PLAYER_DETAIL_SPEC = next(
    spec for spec in TRANSFERMARKT_DETAIL_SPECS if spec.source_name == "players"
)
_ROSTER_LIST_LIMIT = 5000


async def _buffer(rows: AsyncIterator[dict[str, str]]) -> list[dict[str, str]]:
    return [row async for row in rows]


class TransfermarktSyncService:
    def __init__(
        self,
        transfermarkt_client: TransfermarktClientInterface,
        csv_ingestion_service: CsvIngestionService,
        ingestion_repository: IngestionRepositoryInterface,
        ingestion_job_repository: IngestionJobRepositoryInterface,
        team_repository: TeamRepositoryInterface,
        player_repository: PlayerRepositoryInterface,
        identity_link_repository: PlayerIdentityLinkRepositoryInterface,
        roster_scoping_service: RosterScopingService,
        matching_service: PlayerIdentityMatchingService,
        detail_sync: TransfermarktDetailSync,
    ) -> None:
        self._client = transfermarkt_client
        self._csv_ingestion_service = csv_ingestion_service
        self._ingestion_repository = ingestion_repository
        self._ingestion_job_repository = ingestion_job_repository
        self._team_repository = team_repository
        self._player_repository = player_repository
        self._identity_link_repository = identity_link_repository
        self._roster_scoping_service = roster_scoping_service
        self._matching_service = matching_service
        self._detail_sync = detail_sync

    async def run_sync(self, job: IngestionJob) -> IngestionJob:
        # A failure inside _run_pipeline() may originate from a DB statement
        # (e.g. an upsert constraint violation), which leaves the session's
        # transaction aborted -- any further statement on that same session,
        # including a mark_failed() write, fails too until a rollback
        # happens. This service has no direct session access to roll back,
        # so on failure it re-raises the ORIGINAL exception unchanged and
        # lets the caller (which does hold the session) roll back and
        # persist the failure. Do not add a mark_failed()/update() call
        # here -- it silently replaces the real error with a masking one.
        running_job = job.mark_running()
        running_job = await self._ingestion_job_repository.update(running_job)
        row_counts = await self._run_pipeline()
        succeeded_job = running_job.mark_succeeded(row_counts)
        return await self._ingestion_job_repository.update(succeeded_job)

    async def _run_pipeline(self) -> dict[str, int]:
        row_counts: dict[str, int] = {}

        national_team_rows = await _buffer(self._client.stream_csv_rows("national_teams"))
        row_counts["national_teams"] = await self._csv_ingestion_service.ingest_rows(
            _REFERENCE_SPECS_BY_NAME["national_teams"],
            national_team_rows,
            self._ingestion_repository,
        )
        club_rows = await _buffer(self._client.stream_csv_rows("clubs"))
        row_counts["clubs"] = await self._csv_ingestion_service.ingest_rows(
            _REFERENCE_SPECS_BY_NAME["clubs"], club_rows, self._ingestion_repository
        )

        wc2026_teams = await self._team_repository.list(limit=_ROSTER_LIST_LIMIT)
        national_team_id_by_team_id = self._roster_scoping_service.resolve_national_teams(
            wc2026_teams,
            [
                {
                    "national_team_id": int(row["national_team_id"]),
                    "country_name": row["country_name"],
                }
                for row in national_team_rows
            ],
        )

        wc2026_players = await self._player_repository.list(limit=_ROSTER_LIST_LIMIT)
        player_rows = await _buffer(self._client.stream_csv_rows("players"))
        real_player_candidates = self._parse_player_candidates(player_rows)
        candidates = self._matching_service.match(
            wc2026_players, real_player_candidates, national_team_id_by_team_id
        )
        await self._identity_link_repository.upsert_candidates(candidates)

        matched_real_player_ids = {candidate.real_player_id for candidate in candidates}
        matched_player_rows = [
            row for row in player_rows if int(row["player_id"]) in matched_real_player_ids
        ]
        row_counts["players"] = await self._csv_ingestion_service.ingest_rows(
            _PLAYER_DETAIL_SPEC, matched_player_rows, self._ingestion_repository
        )
        matched_real_club_ids = {
            int(row["current_club_id"]) for row in matched_player_rows if row.get("current_club_id")
        }

        row_counts.update(
            await self._detail_sync.sync_player_scoped_tables(matched_real_player_ids)
        )
        row_counts.update(
            await self._detail_sync.sync_match_data(matched_real_player_ids, matched_real_club_ids)
        )
        row_counts["real_player_season_stat"] = await self._detail_sync.sync_season_stats(
            matched_real_player_ids
        )
        return row_counts

    def _parse_player_candidates(self, player_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        # Matching needs typed player_id/date_of_birth, not raw CSV strings.
        # `current_national_team_id` (when present, see module docstring) is
        # passed through as-is; `.get()` in the matching service handles its
        # absence gracefully for rows where it's blank.
        parsed = []
        for row in player_rows:
            entry: dict[str, Any] = dict(row)
            entry["player_id"] = int(row["player_id"])
            entry["date_of_birth"] = parsers.parse_optional_date(row.get("date_of_birth", ""))
            parsed.append(entry)
        return parsed
