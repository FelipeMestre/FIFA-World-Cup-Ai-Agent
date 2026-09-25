"""Admin-triggered clean rematch: wipes `player_identity_link` and
regenerates it from scratch by re-running `PlayerIdentityMatchingService`
against the already-persisted `player` (WC2026 roster) and `real_player`
(Transfermarkt) tables -- no Transfermarkt HTTP calls, no CSV re-parsing,
purely in-DB.

`PlayerIdentityLinkRepository.upsert_candidates` alone cannot produce a
clean result here: its `ON CONFLICT (player_id) DO UPDATE` overwrites every
column, including `status`/`reviewed_by_user_id`, silently stomping admin
approve/reject/reassign decisions for any player still matched, while
leaving a stale row completely untouched for any player no longer matched.
Deleting everything first, then upserting into an empty table, is what
makes the regenerated set an actual clean insert rather than a partial
merge.

Same failure-handling shape as `TransfermarktSyncService.run_sync`: this
service has no direct session access to roll back, so on failure it
re-raises the original exception unchanged and lets the caller (which does
hold the session) roll back and persist the failure. Do not add a
mark_failed()/update() call here.
"""

from typing import Any

from src.domain.ingestion.model.ingestion_job import IngestionJob
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
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
from src.infra.postgres.interfaces.real_player_repository_interface import (
    RealPlayerRepositoryInterface,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema

# The WC2026 roster is a few hundred players (see RosterScopingService's own
# precedent for this same limit) -- unbounded would silently drop players
# past the default page size of 100 if the roster ever grows past it.
_ROSTER_LIST_LIMIT = 5000


class IdentityLinkRematchService:
    def __init__(
        self,
        identity_link_repository: PlayerIdentityLinkRepositoryInterface,
        player_repository: PlayerRepositoryInterface,
        real_player_repository: RealPlayerRepositoryInterface,
        ingestion_repository: IngestionRepositoryInterface,
        ingestion_job_repository: IngestionJobRepositoryInterface,
        matching_service: PlayerIdentityMatchingService,
    ) -> None:
        self._identity_link_repository = identity_link_repository
        self._player_repository = player_repository
        self._real_player_repository = real_player_repository
        self._ingestion_repository = ingestion_repository
        self._ingestion_job_repository = ingestion_job_repository
        self._matching_service = matching_service

    async def rematch(self, job: IngestionJob) -> IngestionJob:
        running_job = job.mark_running()
        running_job = await self._ingestion_job_repository.update(running_job)

        await self._identity_link_repository.delete_all()
        synthetic_players = await self._player_repository.list(limit=_ROSTER_LIST_LIMIT)
        real_player_candidates = await self._real_player_repository.list_match_candidates()
        national_team_id_by_team_id = await self._resolve_national_team_ids()

        candidates = self._matching_service.match(
            synthetic_players, real_player_candidates, national_team_id_by_team_id
        )
        # The table was just wiped, so this is a clean insert set, not a
        # merge onto pre-existing admin decisions.
        upsert_result = await self._identity_link_repository.upsert_candidates(candidates)

        succeeded_job = running_job.mark_succeeded(
            {"player_identity_link": upsert_result.row_count}
        )
        return await self._ingestion_job_repository.update(succeeded_job)

    async def _resolve_national_team_ids(self) -> dict[int, int]:
        # Mirrors TransfermarktSyncService's own resume-mode precedent
        # (skip_populated=True branch) for deriving this exact mapping from
        # already-persisted `national_team` rows, rather than reinventing it:
        # only a row with a non-null transfermarkt_id contributes.
        rows: list[dict[str, Any]] = await self._ingestion_repository.fetch_columns(
            NationalTeamSchema, ["team_id", "transfermarkt_id"]
        )
        return {
            row["team_id"]: row["transfermarkt_id"]
            for row in rows
            if row["transfermarkt_id"] is not None
        }
