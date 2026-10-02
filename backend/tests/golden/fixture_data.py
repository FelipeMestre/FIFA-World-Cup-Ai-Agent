"""Golden-set fixture: a committed, fictional mini tournament.

The golden set pins every known behavior of the chat system to a small dataset whose
facts are written down in this package (never computed by the code under test):

- Layer A (`test_*.py`, default suite): the real tool handlers from
  `build_tool_registry(...)` run on the real repositories against seeded Postgres.
  No LLM, no mocks. Expected values are literals in `expected.py`.
- Layer B (opt-in `llm_eval`) reuses this same fixture through a real LLM.

Run it (needs the local docker Postgres, see `backend/env.example.txt`):

    cd backend && python -m pytest tests/golden -q

The tournament: Valdoria (VLD), Karsovia (KRS) and Sérvenia (SRV, accented name). Valdoria
and Karsovia meet twice (group stage and final, the final decided on penalties); Valdoria
also beats Sérvenia 3-0. Two players share the name "Mateo Ravelli" on different teams.

Seeding contract (shared dev database, which also holds the real dataset):

- Every row lives in a dedicated ID range: `FIXTURE_ID_MIN..FIXTURE_ID_MAX` for WC tables
  and `real_club`, `REAL_ID_MIN..REAL_ID_MAX` for `real_player` and its children (the
  Transfermarkt ID space already has rows in 995000-995999).
- Names are fictional and absent from the real dataset, so resolver queries hit only
  fixture rows. Expected values never depend on rows outside this range (no percentiles).
- Seeding first deletes leftovers in the range, teardown deletes everything again
  (children before parents), and no row outside the range is ever touched.
- Club-career facts assume the dataset's latest known Transfermarkt season is 2025 or
  2026; a newer snapshot would flip the "active" fixture players to retired.
"""

from datetime import date
from typing import NamedTuple

FIXTURE_ID_MIN = 995_000
FIXTURE_ID_MAX = 995_999
REAL_ID_MIN = 99_500_000
REAL_ID_MAX = 99_500_999

LAST_VERIFIED = date(2026, 7, 20)


class TeamSeed(NamedTuple):
    team_id: int
    team_name: str
    fifa_code: str
    confederation: str
    group_letter: str
    fifa_ranking_pre_tournament: int
    elo_rating: int
    manager_name: str


VALDORIA = TeamSeed(995_001, "Valdoria", "VLD", "UEFA", "X", 7, 1810, "Aurelio Benavente")
KARSOVIA = TeamSeed(995_002, "Karsovia", "KRS", "CAF", "X", 15, 1740, "Dmitri Volkonsky")
SERVENIA = TeamSeed(995_003, "Sérvenia", "SRV", "AFC", "X", 31, 1600, "Hana Okabe")
TEAMS = (VALDORIA, KARSOVIA, SERVENIA)

STAGE_GROUP_ID = 995_001
STAGE_FINAL_ID = 995_002
VENUE_ID = 995_001
REFEREE_ID = 995_001
VENUE_NAME = "Estadio Fixture"
VENUE_CITY = "Fixturia"


class PlayerSeed(NamedTuple):
    player_id: int
    team_id: int
    player_name: str
    position: str
    club_team: str
    market_value_eur: int
    caps: int
    date_of_birth: date
    height_cm: int
    goals: int


class StatSeed(NamedTuple):
    player_id: int
    player_name: str
    team_id: int
    position: str
    matches_played: int
    matches_started: int
    minutes_played: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int
    penalty_goals: int
    own_goals: int
    clean_sheets: int | None
    saves: int | None
    goals_conceded: int | None


ORTEGON_ID = 995_001
MONTEFUSCO_ID = 995_002
PENARANDA_ID = 995_003
SANTORINI_ID = 995_004
RAVELLI_VLD_ID = 995_005
RAVELLI_KRS_ID = 995_006
KOZHUKAR_ID = 995_007
FALKENRATH_ID = 995_008
HALDORSEN_ID = 995_009
LINDQVIST_ID = 995_010

_V, _K, _S = VALDORIA.team_id, KARSOVIA.team_id, SERVENIA.team_id

PLAYERS = (
    PlayerSeed(
        ORTEGON_ID,
        _V,
        "Rafael Ortegon",
        "FW",
        "Valdoria City FC",
        60_000_000,
        41,
        date(1999, 3, 12),
        184,
        19,
    ),
    PlayerSeed(
        MONTEFUSCO_ID,
        _V,
        "Dario Montefusco",
        "FW",
        "Valdoria City FC",
        25_000_000,
        12,
        date(2001, 7, 2),
        178,
        4,
    ),
    PlayerSeed(
        PENARANDA_ID,
        _V,
        "Tomás Peñaranda",
        "MF",
        "Harbor United",
        30_000_000,
        28,
        date(1997, 11, 30),
        176,
        3,
    ),
    PlayerSeed(
        SANTORINI_ID,
        _V,
        "Emilio Santorini",
        "GK",
        "Harbor United",
        12_000_000,
        50,
        date(1995, 5, 5),
        192,
        0,
    ),
    PlayerSeed(
        RAVELLI_VLD_ID,
        _V,
        "Mateo Ravelli",
        "DF",
        "Harbor United",
        8_000_000,
        6,
        date(2002, 2, 20),
        181,
        0,
    ),
    PlayerSeed(
        RAVELLI_KRS_ID,
        _K,
        "Mateo Ravelli",
        "FW",
        "Karsovia Dynamo",
        20_000_000,
        33,
        date(1998, 9, 9),
        175,
        11,
    ),
    PlayerSeed(
        KOZHUKAR_ID,
        _K,
        "Pavel Kozhukar",
        "GK",
        "Karsovia Dynamo",
        15_000_000,
        44,
        date(1994, 1, 17),
        195,
        0,
    ),
    # Roster row with no `player_stat`, and no Transfermarkt record by that name.
    PlayerSeed(
        FALKENRATH_ID,
        _S,
        "Nico Falkenrath",
        "DF",
        "Harbor United",
        2_000_000,
        3,
        date(2003, 4, 4),
        183,
        0,
    ),
    # Roster row with no `player_stat`, but a same-named Transfermarkt career.
    PlayerSeed(
        HALDORSEN_ID,
        _S,
        "Bruno Haldorsen",
        "FW",
        "Harbor United",
        5_000_000,
        9,
        date(2000, 6, 6),
        180,
        1,
    ),
    PlayerSeed(
        LINDQVIST_ID,
        _S,
        "Ivo Lindqvist",
        "MF",
        "Harbor United",
        3_000_000,
        15,
        date(1999, 12, 24),
        177,
        0,
    ),
)

STATS = (
    StatSeed(ORTEGON_ID, "Rafael Ortegon", _V, "FW", 3, 3, 270, 4, 1, 1, 0, 1, 0, None, None, None),
    StatSeed(
        MONTEFUSCO_ID, "Dario Montefusco", _V, "FW", 3, 1, 240, 2, 1, 0, 0, 0, 0, None, None, None
    ),
    StatSeed(
        PENARANDA_ID, "Tomás Peñaranda", _V, "MF", 3, 3, 270, 0, 0, 1, 0, 0, 0, None, None, None
    ),
    StatSeed(SANTORINI_ID, "Emilio Santorini", _V, "GK", 3, 3, 270, 0, 0, 0, 0, 0, 0, 1, 11, 2),
    StatSeed(
        RAVELLI_VLD_ID, "Mateo Ravelli", _V, "DF", 3, 3, 270, 0, 0, 0, 0, 0, 0, None, None, None
    ),
    StatSeed(
        RAVELLI_KRS_ID, "Mateo Ravelli", _K, "FW", 2, 2, 175, 2, 0, 0, 1, 0, 0, None, None, None
    ),
    StatSeed(KOZHUKAR_ID, "Pavel Kozhukar", _K, "GK", 2, 2, 180, 0, 0, 0, 0, 0, 0, 0, 15, 3),
    StatSeed(LINDQVIST_ID, "Ivo Lindqvist", _S, "MF", 1, 1, 90, 0, 0, 0, 0, 0, 0, None, None, None),
)
