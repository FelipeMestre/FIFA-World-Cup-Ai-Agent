"""`TableIngestionSpec` instances for the Transfermarkt tables that are
scoped (filtered to the matched WC2026 roster) before ingest: player
profiles, valuations, transfers, and the pure-Transfermarkt-space match data
(`real_game_lineup`, `real_match_event`, `real_club_game`).

`real_player_season_stat` is intentionally NOT declared here: it is fed by
`SeasonStatAggregationService.aggregate(...)`'s grouped output, not a direct
1:1 CSV-to-table mapping.

Several source columns are renamed on the way to their target schema column
(e.g. `market_value_in_eur` -> `market_value_eur`, `height_in_cm` ->
`height_cm`). `TableIngestionSpec.column_spec` keys double as the raw source
CSV column AND the parsed dict key (see `csv_ingestion_service.py`), so
renaming happens via each spec's `row_transform` hook, applied after column
parsing -- not by overloading `column_spec` keys with target names.
"""

from datetime import UTC, datetime
from typing import Any

from src.domain.ingestion.services import csv_parsers as parsers
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.schemas.real_match_data_schema import (
    RealClubGameSchema,
    RealGameLineupSchema,
    RealMatchEventSchema,
)
from src.infra.postgres.schemas.real_player_schema import (
    RealPlayerSchema,
    RealPlayerValuationSchema,
    RealTransferSchema,
)


def _parse_hosting(value: str) -> bool:
    return value.strip().lower() == "home"


def _rename(parsed: dict[str, Any], renames: dict[str, str]) -> dict[str, Any]:
    result = dict(parsed)
    for source_key, target_key in renames.items():
        if source_key in result:
            result[target_key] = result.pop(source_key)
    return result


def _real_player_transform(parsed: dict[str, Any]) -> dict[str, Any]:
    result = _rename(
        parsed,
        {
            "height_in_cm": "height_cm",
            "market_value_in_eur": "market_value_eur",
            "highest_market_value_in_eur": "highest_market_value_eur",
            "url": "profile_url",
        },
    )
    result["last_synced_at"] = datetime.now(UTC)
    return result


def _real_player_valuation_transform(parsed: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        parsed,
        {
            "player_id": "real_player_id",
            "date": "valuation_date",
            "market_value_in_eur": "market_value_eur",
        },
    )


def _real_transfer_transform(parsed: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        parsed,
        {
            "player_id": "real_player_id",
            "transfer_fee": "transfer_fee_eur",
            "market_value_in_eur": "market_value_at_transfer_eur",
        },
    )


def _real_game_lineup_transform(parsed: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        parsed,
        {
            "game_id": "real_game_id",
            "player_id": "real_player_id",
            "club_id": "real_club_id",
            "type": "lineup_type",
            "number": "squad_number",
            "team_captain": "is_captain",
            "date": "lineup_date",
        },
    )


def _real_match_event_transform(parsed: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        parsed,
        {
            "game_id": "real_game_id",
            "type": "event_type",
            "club_id": "real_club_id",
            "player_id": "real_player_id",
            "player_assist_id": "assist_player_id",
            "date": "event_date",
        },
    )


def _real_club_game_transform(parsed: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        parsed,
        {
            "game_id": "real_game_id",
            "club_id": "real_club_id",
            "opponent_id": "opponent_club_id",
            "hosting": "is_home",
        },
    )


TRANSFERMARKT_DETAIL_SPECS: list[TableIngestionSpec] = [
    TableIngestionSpec(
        source_name="players",
        target_schema=RealPlayerSchema,
        column_spec={
            "player_id": parsers.parse_int,
            "first_name": parsers.parse_str,
            "last_name": parsers.parse_str,
            "country_of_birth": parsers.parse_optional_str,
            "country_of_citizenship": parsers.parse_optional_str,
            "date_of_birth": parsers.parse_optional_date,
            "position": parsers.parse_str,
            "sub_position": parsers.parse_optional_str,
            "foot": parsers.parse_optional_str,
            "height_in_cm": parsers.parse_optional_int,
            "current_club_id": parsers.parse_optional_int,
            "contract_expiration_date": parsers.parse_optional_date,
            "market_value_in_eur": parsers.parse_optional_int,
            "highest_market_value_in_eur": parsers.parse_optional_int,
            "url": parsers.parse_str,
        },
        conflict_columns=("player_id",),
        row_transform=_real_player_transform,
    ),
    TableIngestionSpec(
        source_name="player_valuations",
        target_schema=RealPlayerValuationSchema,
        column_spec={
            "player_id": parsers.parse_int,
            "date": parsers.parse_date,
            "market_value_in_eur": parsers.parse_int,
        },
        # NOTE: `real_player_valuation` has no natural-key unique constraint
        # (only a surrogate `id` PK, per the schema's own docstring: upstream
        # can carry same-date duplicate valuations). `ON CONFLICT` requires a
        # matching unique/exclusion constraint on these columns -- flagged as
        # a cross-cutting risk for whichever PR first exercises this spec
        # against a real DB (PR 4's `TransfermarktSyncService`).
        conflict_columns=("real_player_id", "valuation_date"),
        row_transform=_real_player_valuation_transform,
    ),
    TableIngestionSpec(
        source_name="transfers",
        target_schema=RealTransferSchema,
        column_spec={
            "player_id": parsers.parse_int,
            "transfer_date": parsers.parse_date,
            "transfer_season": parsers.parse_optional_str,
            "from_club_id": parsers.parse_optional_int,
            "to_club_id": parsers.parse_optional_int,
            "from_club_name": parsers.parse_str,
            "to_club_name": parsers.parse_str,
            "transfer_fee": parsers.parse_optional_float,
            "market_value_in_eur": parsers.parse_optional_float,
        },
        # Same surrogate-PK caveat as `real_player_valuation` above.
        conflict_columns=("real_player_id", "transfer_date"),
        row_transform=_real_transfer_transform,
    ),
    TableIngestionSpec(
        source_name="game_lineups",
        target_schema=RealGameLineupSchema,
        column_spec={
            "game_lineups_id": parsers.parse_str,
            "game_id": parsers.parse_int,
            "player_id": parsers.parse_int,
            "club_id": parsers.parse_int,
            "type": parsers.parse_str,
            "position": parsers.parse_optional_str,
            "number": parsers.parse_optional_int,
            "team_captain": parsers.parse_bool,
            "date": parsers.parse_optional_date,
        },
        conflict_columns=("game_lineups_id",),
        row_transform=_real_game_lineup_transform,
    ),
    TableIngestionSpec(
        source_name="game_events",
        target_schema=RealMatchEventSchema,
        column_spec={
            "game_event_id": parsers.parse_str,
            "game_id": parsers.parse_int,
            "minute": parsers.parse_optional_int,
            "type": parsers.parse_str,
            "club_id": parsers.parse_optional_int,
            "player_id": parsers.parse_optional_int,
            "description": parsers.parse_optional_str,
            "player_in_id": parsers.parse_optional_int,
            "player_assist_id": parsers.parse_optional_int,
            "date": parsers.parse_optional_date,
        },
        conflict_columns=("game_event_id",),
        row_transform=_real_match_event_transform,
    ),
    TableIngestionSpec(
        source_name="club_games",
        target_schema=RealClubGameSchema,
        column_spec={
            "game_id": parsers.parse_int,
            "club_id": parsers.parse_int,
            "own_goals": parsers.parse_optional_int,
            "own_position": parsers.parse_optional_str,
            "own_manager_name": parsers.parse_optional_str,
            "opponent_id": parsers.parse_optional_int,
            "opponent_goals": parsers.parse_optional_int,
            "opponent_position": parsers.parse_optional_str,
            "opponent_manager_name": parsers.parse_optional_str,
            "hosting": _parse_hosting,
            "is_win": parsers.parse_bool,
        },
        conflict_columns=("real_game_id", "real_club_id"),
        row_transform=_real_club_game_transform,
    ),
]
