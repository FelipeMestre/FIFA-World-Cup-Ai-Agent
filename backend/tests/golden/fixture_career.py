"""Transfermarkt-side half of the golden fixture (`real_*` tables and identity links).

Season labels use the real dataset's four-digit start-year format ("2025"). See
`fixture_data` for the ID-range and cleanup contract.
"""

from datetime import date
from typing import NamedTuple

from tests.golden.fixture_data import (
    FIXTURE_ID_MIN,
    MONTEFUSCO_ID,
    ORTEGON_ID,
    REAL_ID_MIN,
)


class ClubSeed(NamedTuple):
    club_id: int
    club_code: str
    name: str
    url: str


CITY_CLUB = ClubSeed(FIXTURE_ID_MIN + 1, "GVC1", "Valdoria City FC", "https://example.test/c1")
DYNAMO_CLUB = ClubSeed(FIXTURE_ID_MIN + 2, "GKD1", "Karsovia Dynamo", "https://example.test/c2")
HARBOR_CLUB = ClubSeed(FIXTURE_ID_MIN + 3, "GHU1", "Harbor United", "https://example.test/c3")
OLD_CLUB = ClubSeed(FIXTURE_ID_MIN + 4, "GOC1", "Old Boys Retired FC", "https://example.test/c4")
CLUBS = (CITY_CLUB, DYNAMO_CLUB, HARBOR_CLUB, OLD_CLUB)


class RealPlayerSeed(NamedTuple):
    player_id: int
    first_name: str
    last_name: str
    date_of_birth: date | None
    country_of_citizenship: str | None
    position: str
    sub_position: str | None
    foot: str | None
    height_cm: int | None
    current_club_id: int | None
    international_caps: int | None
    international_goals: int | None
    market_value_eur: int | None
    highest_market_value_eur: int | None
    profile_url: str


ORTEGON_REAL_ID = REAL_ID_MIN + 1
MONTEFUSCO_REAL_ID = REAL_ID_MIN + 2
HALDORSEN_REAL_ID = REAL_ID_MIN + 3
VERIDIAN_REAL_ID = REAL_ID_MIN + 4
ORLOWSKI_REAL_ID = REAL_ID_MIN + 5
BANERJEE_REAL_ID = REAL_ID_MIN + 6

_URL = "https://example.test/player"

REAL_PLAYERS = (
    # Approved link to the WC roster player Rafael Ortegon.
    RealPlayerSeed(
        ORTEGON_REAL_ID,
        "Rafael",
        "Ortegon",
        date(1999, 3, 12),
        "Valdoria",
        "Attack",
        "Centre-Forward",
        "left",
        184,
        CITY_CLUB.club_id,
        41,
        19,
        55_000_000,
        70_000_000,
        _URL,
    ),
    # Pending (unreviewed) link to the WC roster player Dario Montefusco.
    RealPlayerSeed(
        MONTEFUSCO_REAL_ID,
        "Dario",
        "Montefusco",
        None,
        None,
        "Attack",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        _URL,
    ),
    # Same name as a WC roster row that has no `player_stat`; never linked.
    RealPlayerSeed(
        HALDORSEN_REAL_ID,
        "Bruno",
        "Haldorsen",
        None,
        None,
        "Attack",
        None,
        None,
        None,
        HARBOR_CLUB.club_id,
        None,
        None,
        None,
        None,
        _URL,
    ),
    # Transfermarkt-only: never at the World Cup, no roster row at all.
    RealPlayerSeed(
        VERIDIAN_REAL_ID,
        "Anselmo",
        "Veridian",
        None,
        None,
        "Attack",
        None,
        None,
        None,
        DYNAMO_CLUB.club_id,
        None,
        None,
        None,
        None,
        _URL,
    ),
    # Last season far behind the dataset's latest: classified retired.
    RealPlayerSeed(
        ORLOWSKI_REAL_ID,
        "Casimir",
        "Orlowski",
        None,
        None,
        "Attack",
        None,
        None,
        None,
        OLD_CLUB.club_id,
        None,
        None,
        None,
        None,
        _URL,
    ),
    # Recent season but no current club: team code FREE.
    RealPlayerSeed(
        BANERJEE_REAL_ID,
        "Teodor",
        "Banerjee",
        None,
        None,
        "Attack",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        _URL,
    ),
)


class SeasonSeed(NamedTuple):
    real_player_id: int
    season: str
    competition_id: str
    appearances: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int
    minutes_played: int


SEASONS = (
    SeasonSeed(ORTEGON_REAL_ID, "2025", "GB1", 30, 18, 6, 3, 0, 2500),
    SeasonSeed(ORTEGON_REAL_ID, "2025", "CL", 8, 5, 1, 1, 0, 640),
    SeasonSeed(ORTEGON_REAL_ID, "2024", "GB1", 28, 12, 7, 2, 0, 2300),
    SeasonSeed(HALDORSEN_REAL_ID, "2025", "GB1", 22, 6, 2, 3, 0, 1700),
    SeasonSeed(HALDORSEN_REAL_ID, "2024", "GB1", 14, 3, 1, 1, 1, 900),
    SeasonSeed(VERIDIAN_REAL_ID, "2025", "ES1", 31, 11, 9, 4, 0, 2700),
    SeasonSeed(ORLOWSKI_REAL_ID, "2008", "ES1", 25, 3, 1, 5, 1, 2000),
    SeasonSeed(BANERJEE_REAL_ID, "2025", "IT1", 12, 1, 0, 0, 0, 900),
)


class TransferSeed(NamedTuple):
    real_player_id: int
    transfer_date: date
    transfer_season: str
    from_club_name: str
    to_club_name: str
    transfer_fee_eur: int
    market_value_at_transfer_eur: int


TRANSFERS = (
    TransferSeed(
        ORTEGON_REAL_ID,
        date(2022, 7, 1),
        "22/23",
        "Harbor United",
        "Valdoria City FC",
        20_000_000,
        30_000_000,
    ),
    TransferSeed(
        ORTEGON_REAL_ID, date(2018, 7, 1), "18/19", "Academia Norte", "Harbor United", 0, 2_000_000
    ),
)


class LinkSeed(NamedTuple):
    player_id: int
    real_player_id: int
    match_method: str
    match_confidence: float
    status: str


LINKS = (
    LinkSeed(ORTEGON_ID, ORTEGON_REAL_ID, "EXACT_NAME_DOB", 1.0, "APPROVED"),
    LinkSeed(MONTEFUSCO_ID, MONTEFUSCO_REAL_ID, "FUZZY_NAME", 0.87, "PENDING"),
)
