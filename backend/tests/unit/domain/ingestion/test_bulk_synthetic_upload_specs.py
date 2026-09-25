"""Pure unit tests for the bulk synthetic upload filename map and fixed
FK-safe ingestion order -- no DB, no HTTP. Confirms the filename -> table
mapping matches `scripts/seed_from_csv.py`'s real dataset filenames exactly
(not a strip-`.csv` heuristic) and that the order places every FK parent
before its children.
"""

from src.domain.ingestion.services.bulk_synthetic_upload_specs import (
    BULK_SYNTHETIC_FILENAME_TO_TABLE,
    BULK_SYNTHETIC_INGESTION_ORDER,
    ingestion_order_index,
    resolve_table_name,
)
from src.domain.ingestion.services.synthetic_table_specs import SYNTHETIC_TABLE_SPECS


def test_resolve_table_name_maps_known_dataset_filenames() -> None:
    assert resolve_table_name("teams.csv") == "team"
    assert resolve_table_name("venues.csv") == "venue"
    assert resolve_table_name("tournament_stages.csv") == "tournament_stage"
    assert resolve_table_name("referees.csv") == "referee"
    assert resolve_table_name("squads_and_players.csv") == "player"
    assert resolve_table_name("matches.csv") == "match"
    assert resolve_table_name("match_events.csv") == "match_event"
    assert resolve_table_name("match_team_stats.csv") == "match_team_stat"
    assert resolve_table_name("match_lineups.csv") == "match_lineup"
    assert resolve_table_name("player_stats.csv") == "player_stat"


def test_resolve_table_name_does_not_guess_from_filename_stem() -> None:
    # `squads_and_players.csv` -> `player` is not derivable by stripping
    # `.csv` -- a naive heuristic would resolve this to `squads_and_players`
    # (or nothing), not `player`. An unrelated file must not silently match.
    assert resolve_table_name("players.csv") is None
    assert resolve_table_name("squads_and_players") is None
    assert resolve_table_name("random_export.csv") is None


def test_ingestion_order_places_fk_parents_before_children() -> None:
    order = BULK_SYNTHETIC_INGESTION_ORDER

    for independent in ("team", "venue", "tournament_stage", "referee"):
        assert order.index(independent) < order.index("player")

    assert order.index("player") < order.index("match")

    for child in ("match_event", "match_team_stat", "match_lineup", "player_stat"):
        assert order.index("match") < order.index(child)


def test_ingestion_order_index_matches_tuple_position() -> None:
    for expected_index, table_name in enumerate(BULK_SYNTHETIC_INGESTION_ORDER):
        assert ingestion_order_index(table_name) == expected_index


def test_bulk_filename_map_covers_every_real_synthetic_table_spec() -> None:
    # Every table `CsvIngestionService` can actually ingest must be reachable
    # by some filename in the bulk map -- otherwise a real dataset file would
    # be silently unroutable through the bulk endpoint.
    spec_names = {spec.source_name for spec in SYNTHETIC_TABLE_SPECS}
    assert set(BULK_SYNTHETIC_FILENAME_TO_TABLE.values()) == spec_names
    assert set(BULK_SYNTHETIC_INGESTION_ORDER) == spec_names
