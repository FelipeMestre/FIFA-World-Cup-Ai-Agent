"""Pure builder functions for `_SqlAlchemyMatchAnalyticsRepository`. Split
out from `match_analytics_repository.py` to keep that file under this
project's 400-line-per-file limit (CLAUDE.md's CODE QUALITY STANDARDS) --
these are the shape-building steps, the repository module itself is only the
SQL-fetching steps and the top-level `get_match_analysis` orchestration.

`player`/`player_stat`/`match_lineup.tactical_position` all store an
abbreviated code (`"FW"`, `"DF"`, `"MF"`, `"GK"`, confirmed against this
codebase's own integration-test fixtures for `player`/`player_stat` in
`player_analytics_repository.py`) rather than the frontend's
`GK`/`DEF`/`MID`/`FWD` literals -- `_normalize_position` maps by first
letter, the same tolerant approach `player_analytics_repository.py` uses.

`match_lineup` has no jersey/squad-number column anywhere in this schema, so
`LineupPlayer.number` can't be a real shirt number here -- `_build_lineup`
assigns a stable 1-based ordinal by `lineup_id` order within each group
instead, documented as a display-only index, not real squad data.

There's likewise no substitution-minute column: a starter's `minutes_played`
is read as the minute they came off, and a used sub's `minutes_played` is
read as the minutes they were on after entering (so their entry minute is
approximated as `_MATCH_DURATION_MINUTES - minutes_played`). Both are
reasonable reads of the existing columns, not exact substitution timestamps.

There's also no formation/shape column -- `_derive_shape` counts the
starting XI's outfield positions (DEF-MID-FWD) as a display-only stand-in for
a real tracked formation.
"""

from src.domain.match_analytics.model.match_analysis import (
    LineupGroup,
    LineupPlayer,
    MatchEvent,
    MatchStatRow,
    PlayerOfMatch,
    Position,
    TeamLineup,
)
from src.infra.postgres.schemas.match_schema import MatchEventSchema, MatchLineupSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema

_MATCH_DURATION_MINUTES = 90

_GOAL_EVENT_TYPES = ("Goal", "Own Goal", "Penalty Shootout Goal")
_CARD_EVENT_TYPES = ("Yellow Card", "Red Card")
_VAR_EVENT_TYPES = ("VAR Review",)

_POSITION_BY_FIRST_LETTER: dict[str, Position] = {
    "G": "GK",
    "D": "DEF",
    "M": "MID",
    "F": "FWD",
}
_POSITION_GROUP_ORDER: tuple[Position, ...] = ("GK", "DEF", "MID", "FWD")

# (display label, `match_team_stat` column, unit suffix)
STAT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Possession", "possession_pct", "%"),
    ("Shots", "total_shots", ""),
    ("On target", "shots_on_target", ""),
    ("Corners", "corners", ""),
    ("Fouls", "fouls", ""),
    ("Offsides", "offsides", ""),
)


def normalize_position(raw_position: str) -> Position:
    first_letter = raw_position.strip()[:1].upper()
    return _POSITION_BY_FIRST_LETTER.get(first_letter, "MID")


def event_kind(event_type: str) -> str | None:
    """`None` for an event type with no widget representation (e.g. a
    shootout miss) -- callers skip building a `MatchEvent` for it."""
    if event_type in _GOAL_EVENT_TYPES:
        return "goal"
    if event_type in _CARD_EVENT_TYPES:
        return "card"
    if event_type in _VAR_EVENT_TYPES:
        return "var"
    return None


def build_stats(home_stat: dict[str, int], away_stat: dict[str, int]) -> list[MatchStatRow]:
    rows = []
    for label, attr, suffix in STAT_FIELDS:
        home_value = home_stat.get(attr, 0)
        away_value = away_stat.get(attr, 0)
        total = home_value + away_value
        home_pct = round((home_value / total) * 100) if total else 50
        rows.append(
            MatchStatRow(
                label=label,
                home_value=f"{home_value}{suffix}",
                away_value=f"{away_value}{suffix}",
                home_pct=home_pct,
            )
        )
    return rows


def build_scorers_text(
    goal_events: list[MatchEventSchema], team_id: int, player_names: dict[int, str]
) -> str:
    entries = [
        f"{player_names.get(e.player_id, 'Unknown')} {e.minute}'"
        for e in goal_events
        if e.team_id == team_id
    ]
    return " · ".join(entries)


def build_events(
    goal_events: list[MatchEventSchema], team_codes: dict[int, str], player_names: dict[int, str]
) -> list[MatchEvent]:
    return [
        MatchEvent(
            minute=f"{e.minute}'",
            kind="goal",
            team_code=team_codes.get(e.team_id, "???"),
            title=player_names.get(e.player_id, "Unknown"),
        )
        for e in goal_events
    ]


def build_timeline(
    events: list[MatchEventSchema],
    team_codes: dict[int, str],
    player_names: dict[int, str],
    assists_by_match_minute_team: dict[tuple[int, int], list[str]],
) -> list[MatchEvent]:
    timeline: list[MatchEvent] = []
    for e in events:
        kind = event_kind(e.event_type)
        if kind is None:
            continue
        player_name = player_names.get(e.player_id, "Unknown")
        team_code = team_codes.get(e.team_id, "???")
        detail = None
        if kind == "goal":
            assist_names = assists_by_match_minute_team.get((e.minute, e.team_id), [])
            if assist_names:
                detail = f"Assist {', '.join(assist_names)}"
        timeline.append(
            MatchEvent(
                minute=f"{e.minute}'",
                kind=kind,
                team_code=team_code,
                title=f"{e.event_type} · {player_name}",
                detail=detail,
            )
        )
    return timeline


def build_player_of_match(
    player: PlayerSchema,
    team_code: str,
    team_name: str,
    goal_count: int,
) -> PlayerOfMatch:
    goal_word = "goal" if goal_count == 1 else "goals"
    return PlayerOfMatch(
        name=player.player_name,
        team_code=team_code,
        position=normalize_position(player.position),
        note=f"{team_name} · {normalize_position(player.position)} · {goal_count} {goal_word}",
    )


def _lineup_mark(row: MatchLineupSchema) -> str | None:
    if row.is_starting_xi:
        if row.minutes_played >= _MATCH_DURATION_MINUTES:
            return None
        return f"▼ {row.minutes_played}'"
    entry_minute = max(_MATCH_DURATION_MINUTES - row.minutes_played, 0)
    return f"▲ {entry_minute}'"


def build_lineup(
    code: str,
    name: str,
    lineup_rows: list[MatchLineupSchema],
    player_names: dict[int, str],
) -> TeamLineup:
    starters = [row for row in lineup_rows if row.is_starting_xi]
    subs_used = [row for row in lineup_rows if not row.is_starting_xi and row.minutes_played > 0]

    groups: list[LineupGroup] = []
    ordinal = 1
    for position in _POSITION_GROUP_ORDER:
        position_rows = [
            row for row in starters if normalize_position(row.tactical_position) == position
        ]
        if not position_rows:
            continue
        players = []
        for row in position_rows:
            players.append(
                LineupPlayer(
                    number=ordinal,
                    name=player_names.get(row.player_id, "Unknown"),
                    mark=_lineup_mark(row),
                )
            )
            ordinal += 1
        groups.append(LineupGroup(name=position, players=players))

    if subs_used:
        players = []
        for row in subs_used:
            players.append(
                LineupPlayer(
                    number=ordinal,
                    name=player_names.get(row.player_id, "Unknown"),
                    mark=_lineup_mark(row),
                )
            )
            ordinal += 1
        groups.append(LineupGroup(name="Subs used", players=players))

    return TeamLineup(code=code, name=name, shape=_derive_shape(starters), groups=groups)


def _derive_shape(starters: list[MatchLineupSchema]) -> str:
    counts = {"DEF": 0, "MID": 0, "FWD": 0}
    for row in starters:
        position = normalize_position(row.tactical_position)
        if position in counts:
            counts[position] += 1
    return f"{counts['DEF']}-{counts['MID']}-{counts['FWD']}"


def build_footer_caption(events: list[MatchEventSchema]) -> str:
    goal_count = sum(1 for e in events if e.event_type in _GOAL_EVENT_TYPES)
    card_count = sum(1 for e in events if e.event_type in _CARD_EVENT_TYPES)
    var_count = sum(1 for e in events if e.event_type in _VAR_EVENT_TYPES)
    parts = [f"{goal_count} goal{'s' if goal_count != 1 else ''}"]
    if card_count:
        parts.append(f"{card_count} card{'s' if card_count != 1 else ''}")
    if var_count:
        parts.append(f"{var_count} VAR review{'s' if var_count != 1 else ''}")
    return " · ".join(parts)


def build_status_label(status: str, has_penalties: bool) -> str:
    label = "Full time" if status == "completed" else status.replace("_", " ").title()
    return f"{label} (pens)" if has_penalties and status == "completed" else label
