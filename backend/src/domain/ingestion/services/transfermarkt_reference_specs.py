"""`TableIngestionSpec` instances for the two Transfermarkt reference tables
ingested in full (no roster scoping applied): national teams and clubs.

Both real source exports carry the column as `total_market_value`, not
`total_market_value_eur` -- verified against the live CSVs (the proposal
always specified this rename; it was missed when this file was first
written, since only `transfermarkt_detail_specs.py` applied renames at the
time). Renamed via `row_transform`, same pattern as the detail specs.
"""

from typing import Any

from src.domain.ingestion.services import csv_parsers as parsers
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.schemas.real_organization_schema import (
    RealClubSchema,
    RealNationalTeamSchema,
)


def _rename_total_market_value(parsed: dict[str, Any]) -> dict[str, Any]:
    result = dict(parsed)
    result["total_market_value_eur"] = result.pop("total_market_value")
    return result


TRANSFERMARKT_REFERENCE_SPECS: list[TableIngestionSpec] = [
    TableIngestionSpec(
        source_name="national_teams",
        target_schema=RealNationalTeamSchema,
        column_spec={
            "national_team_id": parsers.parse_int,
            "name": parsers.parse_str,
            "country_name": parsers.parse_str,
            "confederation": parsers.parse_str,
            "fifa_ranking": parsers.parse_optional_int,
            "squad_size": parsers.parse_optional_int,
            "average_age": parsers.parse_optional_float,
            "total_market_value": parsers.parse_optional_int,
            "coach_name": parsers.parse_optional_str,
            "url": parsers.parse_str,
        },
        conflict_columns=("national_team_id",),
        row_transform=_rename_total_market_value,
    ),
    TableIngestionSpec(
        source_name="clubs",
        target_schema=RealClubSchema,
        column_spec={
            "club_id": parsers.parse_int,
            "club_code": parsers.parse_str,
            "name": parsers.parse_str,
            "domestic_competition_id": parsers.parse_optional_str,
            "total_market_value": parsers.parse_optional_int,
            "squad_size": parsers.parse_optional_int,
            "average_age": parsers.parse_optional_float,
            "stadium_seats": parsers.parse_optional_int,
            "stadium_name": parsers.parse_optional_str,
            "coach_name": parsers.parse_optional_str,
            "url": parsers.parse_str,
        },
        conflict_columns=("club_id",),
        row_transform=_rename_total_market_value,
    ),
]
