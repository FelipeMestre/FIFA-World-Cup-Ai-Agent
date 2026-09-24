"""Dev-only convenience script: bulk-loads the FIFA World Cup 2026 sample
dataset (and an admin user) into Postgres for local development/testing.

This is NOT the future admin HTTP ingestion endpoint -- it's a one-off local
seeding utility. Run `alembic upgrade head` first; this script does not
create tables, it only inserts rows.

Usage:
    venv/bin/python scripts/seed_from_csv.py [--dataset-dir PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from src.domain.auth.services import password_service
from src.infra.postgres.config import engine
from src.infra.postgres.schemas.auth_schema import UserSchema
from src.infra.postgres.schemas.match_schema import (
    MatchEventSchema,
    MatchLineupSchema,
    MatchSchema,
    MatchTeamStatSchema,
)
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema
from src.infra.postgres.schemas.reference_schema import (
    RefereeSchema,
    TournamentStageSchema,
    VenueSchema,
)
from src.infra.postgres.schemas.team_schema import TeamSchema

DEFAULT_DATASET_DIR = Path(__file__).resolve().parents[2] / "data" / "FIFA-World-Cup-2026-Dataset"


def _int(value: str) -> int:
    return int(value)


def _optional_int(value: str) -> int | None:
    return int(value) if value else None


def _float(value: str) -> float:
    return float(value)


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


def _optional_str(value: str) -> str | None:
    return value if value else None


def _bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1"}


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _time(value: str) -> time:
    return time.fromisoformat(value)


ColumnSpec = dict[str, Callable[[str], Any]]

# Ordered so every FK target is seeded before the table that references it:
# team/venue/tournament_stage/referee/player before match, match before its
# child tables, player before player_stat.
TABLE_SPECS: list[tuple[str, Any, ColumnSpec]] = [
    (
        "teams.csv",
        TeamSchema,
        {
            "team_id": _int,
            "team_name": str,
            "fifa_code": str,
            "group_letter": str,
            "confederation": str,
            "fifa_ranking_pre_tournament": _int,
            "elo_rating": _int,
            "manager_name": str,
        },
    ),
    (
        "venues.csv",
        VenueSchema,
        {
            "venue_id": _int,
            "stadium_name": str,
            "city": str,
            "country": str,
            "capacity": _int,
            "latitude": _float,
            "longitude": _float,
            "elevation_meters": _int,
        },
    ),
    (
        "tournament_stages.csv",
        TournamentStageSchema,
        {"stage_id": _int, "stage_name": str, "is_knockout": _bool},
    ),
    (
        "referees.csv",
        RefereeSchema,
        {
            "referee_id": _int,
            "name": str,
            "country": str,
            "avg_cards_per_game": _float,
        },
    ),
    (
        "squads_and_players.csv",
        PlayerSchema,
        {
            "player_id": _int,
            "team_id": _int,
            "player_name": str,
            "position": str,
            "club_team": str,
            "market_value_eur": _int,
            "caps": _int,
            "date_of_birth": _date,
            "height_cm": _int,
            "goals": _int,
        },
    ),
    (
        "matches.csv",
        MatchSchema,
        {
            "match_id": _int,
            "date": _date,
            "kickoff_time_utc": _time,
            "stage_id": _int,
            "venue_id": _int,
            "home_team_id": _int,
            "away_team_id": _int,
            "home_score": _int,
            "away_score": _int,
            "home_penalty_score": _optional_int,
            "away_penalty_score": _optional_int,
            "status": str,
            "result_type": str,
            "home_xg": _float,
            "away_xg": _float,
            "referee_id": _int,
            "player_of_the_match_id": _int,
        },
    ),
    (
        "match_events.csv",
        MatchEventSchema,
        {
            "event_id": _int,
            "match_id": _int,
            "minute": _int,
            "event_type": str,
            "team_id": _int,
            "player_id": _int,
        },
    ),
    (
        "match_team_stats.csv",
        MatchTeamStatSchema,
        {
            "match_id": _int,
            "team_id": _int,
            "possession_pct": _int,
            "total_shots": _int,
            "shots_on_target": _int,
            "corners": _int,
            "fouls": _int,
            "offsides": _int,
            "saves": _int,
            "player_of_the_match": _optional_str,
            "data_source": str,
            "last_updated": _date,
        },
    ),
    (
        "match_lineups.csv",
        MatchLineupSchema,
        {
            "lineup_id": _int,
            "match_id": _int,
            "player_id": _int,
            "team_id": _int,
            "is_starting_xi": _bool,
            "tactical_position": str,
            "minutes_played": _int,
        },
    ),
    (
        "player_stats.csv",
        PlayerStatSchema,
        {
            "player_id": _int,
            "player_name": str,
            "team_id": _int,
            "position": str,
            "matches_played": _int,
            "matches_started": _int,
            "minutes_played": _int,
            "goals": _int,
            "assists": _int,
            "shots": _optional_int,
            "shots_on_target": _optional_int,
            "yellow_cards": _int,
            "red_cards": _int,
            "penalty_goals": _int,
            "own_goals": _int,
            "clean_sheets": _optional_int,
            "saves": _optional_int,
            "goals_conceded": _optional_int,
            "average_rating": _optional_float,
            "data_source": _optional_str,
            "last_verified": _date,
        },
    ),
]


def _load_rows(csv_path: Path, column_spec: ColumnSpec) -> list[dict[str, Any]]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [
            {column: parser(row[column]) for column, parser in column_spec.items()}
            for row in reader
        ]


async def _seed_dataset_tables(dataset_dir: Path) -> None:
    async with engine.begin() as conn:
        for filename, schema_cls, column_spec in TABLE_SPECS:
            rows = _load_rows(dataset_dir / filename, column_spec)
            if not rows:
                continue
            await conn.execute(schema_cls.__table__.insert(), rows)
            print(f"seeded {len(rows):>5} rows into {schema_cls.__tablename__} ({filename})")


async def _seed_admin_user(email: str, password: str) -> None:
    async with engine.begin() as conn:
        row = {
            "email": email,
            "name": os.environ.get("SEED_ADMIN_NAME") or "Felipe Mestre",
            "password_hash": password_service.hash_password(password),
            "is_admin": True,
            "created_at": datetime.now(UTC),
        }
        await conn.execute(UserSchema.__table__.insert(), [row])
        print(f"seeded admin user {email}")


async def main(dataset_dir: Path) -> None:
    await _seed_dataset_tables(dataset_dir)

    admin_email = os.environ.get("SEED_ADMIN_EMAIL")
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    if admin_email and admin_password:
        await _seed_admin_user(admin_email, admin_password)
    else:
        print("SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD not set, skipping admin user seed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    args = parser.parse_args()
    asyncio.run(main(args.dataset_dir))
