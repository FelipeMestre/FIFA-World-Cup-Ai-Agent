"""Filename -> target-table map and fixed FK-safe ingestion order for the
bulk synthetic CSV upload endpoint. Reuses the exact filename/table pairing
already established in `scripts/seed_from_csv.py`'s `TABLE_SPECS` --
deliberately a static map, not a strip-`.csv` heuristic, so a renamed or
unrelated file is rejected instead of being silently guess-routed to the
wrong table (e.g. `squads_and_players.csv` -> `player`, not
`squads_and_players`).
"""

from __future__ import annotations

# 1:1 with `scripts/seed_from_csv.py`'s `TABLE_SPECS` filenames. Every value
# must be a `source_name` present in `SYNTHETIC_TABLE_SPECS` -- enforced by
# the assertion below rather than left to drift silently.
BULK_SYNTHETIC_FILENAME_TO_TABLE: dict[str, str] = {
    "teams.csv": "team",
    "venues.csv": "venue",
    "tournament_stages.csv": "tournament_stage",
    "referees.csv": "referee",
    "squads_and_players.csv": "player",
    "matches.csv": "match",
    "match_events.csv": "match_event",
    "match_team_stats.csv": "match_team_stat",
    "match_lineups.csv": "match_lineup",
    "player_stats.csv": "player_stat",
}

# Fixed FK-safe ingestion order: independent reference tables first, then
# `player` (needs `team`), then `match` (needs team/venue/tournament_stage/
# referee, plus a nullable FK to `player` for player-of-the-match), then the
# match-scoped child tables (need `match`/`team`/`player`). Tables within the
# same tier may be ingested in either relative order -- only cross-tier order
# matters for foreign keys.
BULK_SYNTHETIC_INGESTION_ORDER: tuple[str, ...] = (
    "team",
    "venue",
    "tournament_stage",
    "referee",
    "player",
    "match",
    "match_event",
    "match_team_stat",
    "match_lineup",
    "player_stat",
)

if set(BULK_SYNTHETIC_FILENAME_TO_TABLE.values()) != set(BULK_SYNTHETIC_INGESTION_ORDER):
    raise AssertionError(
        "BULK_SYNTHETIC_INGESTION_ORDER must contain exactly the table names "
        "in BULK_SYNTHETIC_FILENAME_TO_TABLE.values(), no more, no less"
    )


def resolve_table_name(filename: str) -> str | None:
    """Looks up the target table for an uploaded filename, or `None` if the
    filename is not a recognized synthetic dataset export. Never guesses --
    an unrecognized filename must be rejected by the caller, not routed by a
    heuristic.
    """
    return BULK_SYNTHETIC_FILENAME_TO_TABLE.get(filename)


def ingestion_order_index(table_name: str) -> int:
    """Position of `table_name` in the fixed FK-safe ingestion order. Raises
    `ValueError` for a table name outside that order -- callers only pass
    table names already resolved via `resolve_table_name`, so an unknown
    name here signals a bug, not bad user input.
    """
    return BULK_SYNTHETIC_INGESTION_ORDER.index(table_name)
