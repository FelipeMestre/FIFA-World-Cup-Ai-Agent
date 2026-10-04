"""Deliberately empty entities for the no-data tests (see `no_data_cases` for the map).

Every row lives in the same dedicated ID ranges as the rest of the golden fixture (contract:
see `fixture_data`) and is seeded and torn down by the same code in `seeding`. Nothing here
touches the three story teams, so the story facts in `expected` stay valid.

- Ostravia: has a roster but never played. Its keeper has a stat row with 0 minutes and no
  saves/clean-sheet/goals-conceded measurement (NULL); its midfielder has a stat row of
  zeros and an approved Transfermarkt link whose career holds no seasons and no transfers.
- Thalmoor: no roster and no matches at all.
- Varnholm vs Quellis: one `scheduled` match with no events, team stats or lineups. The
  schema requires a score, a venue and a Player of the Match, so those exist (0-0, the
  fixture venue, and a Varnholm defender who has no `player_stat` row).
- Thorncastle: a Transfermarkt player with no club, no seasons and no transfers. Searching
  his name finds this record directly; the approved link above reaches it from Tavish.
"""

from datetime import date, time
from typing import NamedTuple

from tests.golden.fixture_career import LinkSeed, RealPlayerSeed
from tests.golden.fixture_data import (
    REAL_ID_MIN,
    STAGE_GROUP_ID,
    PlayerSeed,
    StatSeed,
    TeamSeed,
)

OSTRAVIA = TeamSeed(995_004, "Ostravia", "OST", "UEFA", "Y", 40, 1500, "Selma Ardenwood")
THALMOOR = TeamSeed(995_005, "Thalmoor", "THM", "CAF", "Y", 55, 1400, "Petr Oakhollow")
VARNHOLM = TeamSeed(995_006, "Varnholm", "VRN", "AFC", "Z", 60, 1350, "Ilse Brightwater")
QUELLIS = TeamSeed(995_007, "Quellis", "QLS", "CONCACAF", "Z", 65, 1300, "Anton Stillmere")
EMPTY_TEAMS = (OSTRAVIA, THALMOOR, VARNHOLM, QUELLIS)

QUILLFEATHER_ID = 995_011
TAVISH_ID = 995_012
DUNMORE_ID = 995_013

EMPTY_PLAYERS = (
    PlayerSeed(
        QUILLFEATHER_ID,
        OSTRAVIA.team_id,
        "Zeno Quillfeather",
        "GK",
        "Harbor United",
        1_000_000,
        2,
        date(2001, 8, 8),
        190,
        0,
    ),
    PlayerSeed(
        TAVISH_ID,
        OSTRAVIA.team_id,
        "Orin Tavish",
        "MF",
        "Harbor United",
        1_500_000,
        4,
        date(2000, 10, 10),
        179,
        0,
    ),
    PlayerSeed(
        DUNMORE_ID,
        VARNHOLM.team_id,
        "Kestrel Dunmore",
        "DF",
        "Harbor United",
        900_000,
        1,
        date(2002, 1, 11),
        182,
        0,
    ),
)

_O = OSTRAVIA.team_id

EMPTY_STATS = (
    # 0 minutes, and saves / clean sheets / goals conceded never measured (NULL).
    StatSeed(
        QUILLFEATHER_ID, "Zeno Quillfeather", _O, "GK", 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None, None
    ),
    StatSeed(TAVISH_ID, "Orin Tavish", _O, "MF", 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None, None),
)


class ScheduledMatchSeed(NamedTuple):
    match_id: int
    match_date: date
    kickoff: time
    stage_id: int
    home_team_id: int
    away_team_id: int
    status: str
    potm_id: int


SCHEDULED_VRN_QLS_ID = 995_004

SCHEDULED_MATCHES = (
    ScheduledMatchSeed(
        SCHEDULED_VRN_QLS_ID,
        date(2026, 7, 1),
        time(15, 0),
        STAGE_GROUP_ID,
        VARNHOLM.team_id,
        QUELLIS.team_id,
        "scheduled",
        DUNMORE_ID,
    ),
)

THORNCASTLE_REAL_ID = REAL_ID_MIN + 7

EMPTY_REAL_PLAYERS = (
    RealPlayerSeed(
        THORNCASTLE_REAL_ID,
        "Wendell",
        "Thorncastle",
        None,
        None,
        "Defender",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "https://example.test/player",
    ),
)

# Approved link from Tavish to a Transfermarkt record that holds no seasons or transfers.
EMPTY_LINKS = (LinkSeed(TAVISH_ID, THORNCASTLE_REAL_ID, "EXACT_NAME_DOB", 1.0, "APPROVED"),)
