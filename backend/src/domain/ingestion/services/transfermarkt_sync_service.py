"""Top-level Transfermarkt sync orchestrator: reference ingest -> team-level
scoping -> identity matching -> detail pulls (delegated to
`TransfermarktDetailSync`), updating the `IngestionJob` throughout.

Every player `players.csv` carries is persisted to `real_player` regardless
of whether it matched a WC2026 roster player -- Transfermarkt is a full data
source in its own right, not just a lookup table for identity matching.
Identity matching still runs over the same buffered rows to populate
`player_identity_link`, but it no longer gates what gets ingested.

Correction (verified against the live source): `players.csv` DOES carry
`current_national_team_id` -- an earlier revision of this module assumed
otherwise without checking the real export.
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
from src.domain.ingestion.services.transfermarkt_detail_sync import (
    TransfermarktDetailSync,
    _sanitize_club_reference,
)
from src.domain.ingestion.services.transfermarkt_reference_specs import (
    TRANSFERMARKT_REFERENCE_SPECS,
)
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
)
from src.infra.postgres.interfaces.national_team_repository_interface import (
    NationalTeamRepositoryInterface,
)
from src.infra.postgres.interfaces.player_identity_link_repository_interface import (
    PlayerIdentityLinkRepositoryInterface,
)
from src.infra.postgres.interfaces.player_repository_interface import PlayerRepositoryInterface
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.real_organization_schema import RealClubSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSchema
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
        national_team_repository: NationalTeamRepositoryInterface,
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
        self._national_team_repository = national_team_repository
        self._player_repository = player_repository
        self._identity_link_repository = identity_link_repository
        self._roster_scoping_service = roster_scoping_service
        self._matching_service = matching_service
        self._detail_sync = detail_sync

    async def run_sync(self, job: IngestionJob, skip_populated: bool = False) -> IngestionJob:
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
        row_counts = await self._run_pipeline(skip_populated)
        succeeded_job = running_job.mark_succeeded(row_counts)
        return await self._ingestion_job_repository.update(succeeded_job)

    async def _run_pipeline(self, skip_populated: bool) -> dict[str, int]:
        row_counts: dict[str, int] = {}

        # `national_team` base rows come only from the synthetic WC2026
        # upload, never from this sync -- fetch them first so the
        # Transfermarkt step below can match against them.
        wc2026_teams = await self._national_team_repository.list(limit=_ROSTER_LIST_LIMIT)

        # Resume mode: a step whose target table is already populated is
        # skipped -- its (often expensive: players.csv alone is ~50k rows
        # feeding an O(n*m) fuzzy-match loop) fetch+parse+match+upsert never
        # runs. Whatever a later step needs from a skipped one is rebuilt
        # from the already-persisted rows instead of the source CSV.
        #
        # `national_team` rows always exist once the synthetic upload has
        # run (independent of this sync), so `has_rows` can't signal
        # whether Transfermarkt enrichment already happened here -- the
        # signal is instead whether any row has been matched/enriched yet.
        if skip_populated and await self._ingestion_repository.has_non_null_column(
            NationalTeamSchema, "transfermarkt_id"
        ):
            enriched = await self._ingestion_repository.fetch_columns(
                NationalTeamSchema, ["team_id", "transfermarkt_id"]
            )
            national_team_id_by_team_id = {
                row["team_id"]: row["transfermarkt_id"]
                for row in enriched
                if row["transfermarkt_id"] is not None
            }
            row_counts["national_teams"] = 0
        else:
            national_team_rows = await _buffer(self._client.stream_csv_rows("national_teams"))
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
            real_row_by_id = {int(row["national_team_id"]): row for row in national_team_rows}

            def _enrichment_columns(real_team_id: int) -> dict[str, Any]:
                row = real_row_by_id[real_team_id]
                return {
                    "squad_size": parsers.parse_optional_int(row.get("squad_size", "")),
                    "average_age": parsers.parse_optional_float(row.get("average_age", "")),
                    "total_market_value_eur": parsers.parse_optional_int(
                        row.get("total_market_value", "")
                    ),
                    "url": parsers.parse_optional_str(row.get("url", "")),
                }

            # A Transfermarkt country matched to an existing WC2026 team_id
            # (by name, via RosterScopingService) only gets that row's
            # enrichment columns UPDATEd. A country with no WC2026 match is
            # CREATEd instead -- `team_id` is deliberately left out of the
            # payload so the database's IDENTITY column assigns it, and
            # `transfermarkt_id` (unique) is the natural key a later sync
            # re-matches this same row by, so it's never duplicated.
            update_rows = [
                {
                    "team_id": team_id,
                    "transfermarkt_id": real_team_id,
                    **_enrichment_columns(real_team_id),
                }
                for team_id, real_team_id in national_team_id_by_team_id.items()
            ]
            update_result = await self._ingestion_repository.update_matched(
                NationalTeamSchema, "team_id", update_rows
            )

            matched_transfermarkt_ids = set(national_team_id_by_team_id.values())
            create_rows = [
                {
                    "team_name": row["country_name"],
                    "confederation": row["confederation"],
                    "transfermarkt_id": int(row["national_team_id"]),
                    **_enrichment_columns(int(row["national_team_id"])),
                }
                for row in national_team_rows
                if int(row["national_team_id"]) not in matched_transfermarkt_ids
            ]
            create_result = await self._ingestion_repository.upsert_many(
                NationalTeamSchema, create_rows, conflict_columns=("transfermarkt_id",)
            )
            row_counts["national_teams"] = update_result.row_count + create_result.row_count

        if skip_populated and await self._ingestion_repository.has_rows(RealClubSchema):
            known_club_ids = {
                str(row["club_id"])
                for row in await self._ingestion_repository.fetch_columns(
                    RealClubSchema, ["club_id"]
                )
            }
            row_counts["clubs"] = 0
        else:
            club_rows = await _buffer(self._client.stream_csv_rows("clubs"))
            row_counts["clubs"] = await self._csv_ingestion_service.ingest_rows(
                _REFERENCE_SPECS_BY_NAME["clubs"], club_rows, self._ingestion_repository
            )
            # A player/transfer/match row can reference a club_id that isn't
            # in this particular clubs.csv export (Transfermarkt's own data
            # gap, e.g. an obscure or historical club never scraped into
            # this file) -- found live: real_player_current_club_id_fkey
            # failed on a club_id that simply doesn't exist in real_club.
            # club_id columns are nullable throughout the real_* schema
            # specifically to allow this; unresolvable references are
            # nulled out rather than dropping the row or relaxing the
            # constraint.
            known_club_ids = {row["club_id"] for row in club_rows}

        if skip_populated and await self._ingestion_repository.has_rows(RealPlayerSchema):
            persisted_players = await self._ingestion_repository.fetch_columns(
                RealPlayerSchema, ["player_id", "current_club_id"]
            )
            all_real_player_ids = {row["player_id"] for row in persisted_players}
            all_real_club_ids = {
                row["current_club_id"]
                for row in persisted_players
                if row["current_club_id"] is not None
            }
            row_counts["players"] = 0
        else:
            wc2026_players = await self._player_repository.list(limit=_ROSTER_LIST_LIMIT)
            player_rows = await _buffer(self._client.stream_csv_rows("players"))
            real_player_candidates = self._parse_player_candidates(player_rows)
            candidates = self._matching_service.match(
                wc2026_players, real_player_candidates, national_team_id_by_team_id
            )

            # Every Transfermarkt player is persisted, not only ones a
            # WC2026 roster player matched to -- Transfermarkt is a full
            # data source in its own right (stats, valuations, transfers),
            # not just a lookup table for identity matching.
            sanitized_player_rows = [
                _sanitize_club_reference(row, "current_club_id", known_club_ids)
                for row in player_rows
            ]
            # `player_identity_link.real_player_id` has a foreign key into
            # `real_player` -- the real_player rows must exist before
            # upserting identity-link candidates that reference them, or
            # the insert fails with ForeignKeyViolationError (found live:
            # this ordering bug surfaced immediately after fixing the
            # same-batch real_player_id collision above).
            row_counts["players"] = await self._csv_ingestion_service.ingest_rows(
                _PLAYER_DETAIL_SPEC, sanitized_player_rows, self._ingestion_repository
            )
            all_real_player_ids = {int(row["player_id"]) for row in player_rows}
            # Sanitized above, so any surviving current_club_id is
            # known-valid -- this scope set is itself safe to use as a
            # filter for club_games/game_lineups/game_events below.
            all_real_club_ids = {
                int(row["current_club_id"])
                for row in sanitized_player_rows
                if row.get("current_club_id")
            }

            await self._identity_link_repository.upsert_candidates(candidates)

        row_counts.update(
            await self._detail_sync.sync_player_scoped_tables(
                all_real_player_ids, known_club_ids, skip_populated
            )
        )
        row_counts.update(
            await self._detail_sync.sync_match_data(
                all_real_player_ids, all_real_club_ids, known_club_ids, skip_populated
            )
        )
        row_counts["real_player_season_stat"] = await self._detail_sync.sync_season_stats(
            all_real_player_ids, skip_populated
        )
        return row_counts

    def _parse_player_candidates(self, player_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        # Matching needs typed player_id/date_of_birth/height_in_cm/
        # current_national_team_id, not raw CSV strings -- leaving any of
        # these as strings makes every comparison against the synthetic
        # player's typed fields silently False (found live: this broke both
        # the EXACT_NAME_TEAM tier and fuzzy-match DOB+height corroboration
        # until fixed here).
        parsed = []
        for row in player_rows:
            entry: dict[str, Any] = dict(row)
            entry["player_id"] = int(row["player_id"])
            entry["date_of_birth"] = parsers.parse_optional_date(row.get("date_of_birth", ""))
            entry["height_in_cm"] = parsers.parse_optional_int(row.get("height_in_cm", ""))
            entry["current_national_team_id"] = parsers.parse_optional_int(
                row.get("current_national_team_id", "")
            )
            parsed.append(entry)
        return parsed
