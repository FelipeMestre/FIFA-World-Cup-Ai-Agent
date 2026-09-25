"""Ordered checkpoint stages of a bulk synthetic CSV upload job, one per
target table ingested. Values match `BULK_SYNTHETIC_INGESTION_ORDER`
(and each `ResolvedFile.table_name`, itself a `TableIngestionSpec.source_name`)
so a stage and its `row_counts` entry line up under the same name -- mirrors
`TransfermarktSyncStage`'s same convention for the Transfermarkt sync job.
"""

from enum import StrEnum


class BulkSyntheticUploadStage(StrEnum):
    TEAM = "team"
    VENUE = "venue"
    TOURNAMENT_STAGE = "tournament_stage"
    REFEREE = "referee"
    PLAYER = "player"
    MATCH = "match"
    MATCH_EVENT = "match_event"
    MATCH_TEAM_STAT = "match_team_stat"
    MATCH_LINEUP = "match_lineup"
    PLAYER_STAT = "player_stat"
