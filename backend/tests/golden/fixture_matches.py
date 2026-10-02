"""Match half of the golden fixture: matches, team stats, events and lineups.

See `fixture_data` for the story, the ID-range and the cleanup contract.
"""

from datetime import date, time
from typing import NamedTuple

from tests.golden.fixture_data import (
    KARSOVIA,
    KOZHUKAR_ID,
    MONTEFUSCO_ID,
    ORTEGON_ID,
    PENARANDA_ID,
    RAVELLI_KRS_ID,
    SANTORINI_ID,
    SERVENIA,
    STAGE_FINAL_ID,
    STAGE_GROUP_ID,
    VALDORIA,
)

_V, _K, _S = VALDORIA.team_id, KARSOVIA.team_id, SERVENIA.team_id


class MatchSeed(NamedTuple):
    match_id: int
    match_date: date
    kickoff: time
    stage_id: int
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    home_penalty_score: int | None
    away_penalty_score: int | None
    home_xg: float
    away_xg: float
    potm_id: int


GROUP_VLD_KRS_ID = 995_001
FINAL_KRS_VLD_ID = 995_002
GROUP_SRV_VLD_ID = 995_003

MATCHES = (
    MatchSeed(
        GROUP_VLD_KRS_ID,
        date(2026, 6, 14),
        time(18, 0),
        STAGE_GROUP_ID,
        _V,
        _K,
        2,
        1,
        None,
        None,
        1.9,
        0.8,
        ORTEGON_ID,
    ),
    MatchSeed(
        FINAL_KRS_VLD_ID,
        date(2026, 7, 19),
        time(19, 0),
        STAGE_FINAL_ID,
        _K,
        _V,
        1,
        1,
        4,
        3,
        1.1,
        1.3,
        KOZHUKAR_ID,
    ),
    MatchSeed(
        GROUP_SRV_VLD_ID,
        date(2026, 6, 20),
        time(16, 0),
        STAGE_GROUP_ID,
        _S,
        _V,
        0,
        3,
        None,
        None,
        0.4,
        2.6,
        MONTEFUSCO_ID,
    ),
)


class TeamStatSeed(NamedTuple):
    match_id: int
    team_id: int
    possession_pct: int
    total_shots: int
    shots_on_target: int
    corners: int
    fouls: int
    offsides: int
    saves: int


TEAM_STATS = (
    TeamStatSeed(GROUP_VLD_KRS_ID, _V, 58, 14, 6, 7, 9, 2, 3),
    TeamStatSeed(GROUP_VLD_KRS_ID, _K, 42, 8, 3, 3, 12, 1, 4),
    TeamStatSeed(FINAL_KRS_VLD_ID, _K, 47, 9, 4, 4, 10, 3, 5),
    TeamStatSeed(FINAL_KRS_VLD_ID, _V, 53, 10, 4, 5, 11, 2, 3),
    TeamStatSeed(GROUP_SRV_VLD_ID, _S, 40, 5, 1, 2, 14, 3, 6),
    TeamStatSeed(GROUP_SRV_VLD_ID, _V, 60, 16, 9, 8, 7, 1, 1),
)


class EventSeed(NamedTuple):
    event_id: int
    match_id: int
    minute: int
    event_type: str
    team_id: int
    player_id: int


EVENTS = (
    EventSeed(995_001, GROUP_VLD_KRS_ID, 23, "Goal", _V, ORTEGON_ID),
    EventSeed(995_002, GROUP_VLD_KRS_ID, 23, "Assist", _V, MONTEFUSCO_ID),
    EventSeed(995_003, GROUP_VLD_KRS_ID, 40, "Yellow Card", _V, PENARANDA_ID),
    EventSeed(995_004, GROUP_VLD_KRS_ID, 55, "Goal", _K, RAVELLI_KRS_ID),
    EventSeed(995_005, GROUP_VLD_KRS_ID, 78, "Goal", _V, ORTEGON_ID),
    EventSeed(995_006, FINAL_KRS_VLD_ID, 12, "Goal", _K, RAVELLI_KRS_ID),
    EventSeed(995_007, FINAL_KRS_VLD_ID, 70, "Yellow Card", _V, ORTEGON_ID),
    EventSeed(995_008, FINAL_KRS_VLD_ID, 85, "Red Card", _K, RAVELLI_KRS_ID),
    EventSeed(995_009, FINAL_KRS_VLD_ID, 88, "Goal", _V, MONTEFUSCO_ID),
    EventSeed(995_010, FINAL_KRS_VLD_ID, 88, "Assist", _V, ORTEGON_ID),
    EventSeed(995_011, GROUP_SRV_VLD_ID, 10, "Goal", _V, ORTEGON_ID),
    EventSeed(995_012, GROUP_SRV_VLD_ID, 60, "Goal", _V, ORTEGON_ID),
    EventSeed(995_013, GROUP_SRV_VLD_ID, 80, "Goal", _V, MONTEFUSCO_ID),
)


class LineupSeed(NamedTuple):
    lineup_id: int
    match_id: int
    player_id: int
    team_id: int
    is_starting_xi: bool
    tactical_position: str
    minutes_played: int


LINEUPS = (
    LineupSeed(995_001, GROUP_VLD_KRS_ID, SANTORINI_ID, _V, True, "GK", 90),
    LineupSeed(995_002, GROUP_VLD_KRS_ID, PENARANDA_ID, _V, True, "MF", 64),
    LineupSeed(995_003, GROUP_VLD_KRS_ID, ORTEGON_ID, _V, True, "FW", 90),
    LineupSeed(995_004, GROUP_VLD_KRS_ID, MONTEFUSCO_ID, _V, False, "FW", 26),
    LineupSeed(995_005, GROUP_VLD_KRS_ID, KOZHUKAR_ID, _K, True, "GK", 90),
    LineupSeed(995_006, GROUP_VLD_KRS_ID, RAVELLI_KRS_ID, _K, True, "FW", 90),
    LineupSeed(995_007, FINAL_KRS_VLD_ID, KOZHUKAR_ID, _K, True, "GK", 120),
    LineupSeed(995_008, FINAL_KRS_VLD_ID, RAVELLI_KRS_ID, _K, True, "FW", 85),
    LineupSeed(995_009, FINAL_KRS_VLD_ID, SANTORINI_ID, _V, True, "GK", 120),
    LineupSeed(995_010, FINAL_KRS_VLD_ID, ORTEGON_ID, _V, True, "FW", 120),
)
