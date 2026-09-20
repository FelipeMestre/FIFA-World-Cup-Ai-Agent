"""Guards the national_teams/clubs column rename against a regression: the
real Transfermarkt exports carry `total_market_value` (no `_eur` suffix),
verified against the live source -- this diverges from the earlier column
name assumed here.
"""

from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.transfermarkt_reference_specs import (
    TRANSFERMARKT_REFERENCE_SPECS,
)
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.real_organization_schema import RealNationalTeamSchema


class _FakeIngestionRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[type, list[dict]]] = []

    async def upsert_many(self, schema_cls, rows, conflict_columns) -> UpsertResult:
        self.calls.append((schema_cls, rows))
        return UpsertResult(table_name=schema_cls.__tablename__, row_count=len(rows))


async def test_national_teams_spec_renames_total_market_value_to_eur_suffix():
    spec = next(s for s in TRANSFERMARKT_REFERENCE_SPECS if s.source_name == "national_teams")
    row = {
        "national_team_id": "1",
        "name": "Testland",
        "country_name": "Testland",
        "confederation": "UEFA",
        "fifa_ranking": "10",
        "squad_size": "23",
        "average_age": "27.0",
        "total_market_value": "100000000",
        "coach_name": "",
        "url": "https://example.test",
    }
    repository = _FakeIngestionRepository()

    await CsvIngestionService().ingest_rows(spec, [row], repository)

    schema_cls, rows = repository.calls[0]
    assert schema_cls is RealNationalTeamSchema
    assert rows[0]["total_market_value_eur"] == 100000000
    assert "total_market_value" not in rows[0]


async def test_clubs_spec_handles_blank_total_market_value():
    spec = next(s for s in TRANSFERMARKT_REFERENCE_SPECS if s.source_name == "clubs")
    row = {
        "club_id": "10",
        "club_code": "test-fc",
        "name": "Test FC",
        "domestic_competition_id": "L1",
        "total_market_value": "",
        "squad_size": "25",
        "average_age": "26.0",
        "stadium_seats": "30000",
        "stadium_name": "Test Arena",
        "coach_name": "",
        "url": "https://example.test",
    }
    repository = _FakeIngestionRepository()

    await CsvIngestionService().ingest_rows(spec, [row], repository)

    _, rows = repository.calls[0]
    assert rows[0]["total_market_value_eur"] is None
