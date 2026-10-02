"""Builder for a valid `MatchAnalysis` carrying altered values."""

from src.domain.match_analytics.model.match_analysis import (
    LineupGroup,
    LineupPlayer,
    MatchAnalysis,
    MatchEvent,
    MatchStatRow,
    PlayerOfMatch,
    TeamLineup,
    TeamRef,
)

HOME_CODE = "ARG"
AWAY_CODE = "FRA"


def _goal_event(minute: str, team_code: str, scorer: str) -> MatchEvent:
    return MatchEvent(minute=minute, kind="goal", team_code=team_code, title=f"Goal: {scorer}")


def _lineup(code: str, name: str) -> TeamLineup:
    return TeamLineup(
        code=code,
        name=name,
        shape="4-3-3",
        groups=[LineupGroup(name="GK", players=[LineupPlayer(number=1, name=f"{name} Keeper")])],
    )


def build_match_analysis(
    *,
    home_score: int,
    away_score: int,
    home_scorer: str,
    away_scorer: str,
    player_of_match: str,
    stage_label: str = "Final",
) -> MatchAnalysis:
    """A `MatchAnalysis` whose score, scorers and Player of the Match are set by
    the test, repeated in the scoreboard, scorer strings, events and timeline.
    """
    events = [
        _goal_event("23'", HOME_CODE, home_scorer),
        _goal_event("67'", AWAY_CODE, away_scorer),
    ]
    return MatchAnalysis(
        id="700001",
        stage_label=stage_label,
        date_label="19 Jul 2026",
        venue_label="MetLife Stadium",
        home_team=TeamRef(code=HOME_CODE, name="Argentina"),
        away_team=TeamRef(code=AWAY_CODE, name="France"),
        home_score=home_score,
        away_score=away_score,
        status_label="Full time",
        home_scorers=f"{home_scorer} 23'",
        away_scorers=f"{away_scorer} 67'",
        stats=[MatchStatRow(label="Possession", home_value="55%", away_value="45%", home_pct=55)],
        events=events,
        player_of_match=PlayerOfMatch(
            name=player_of_match,
            team_code=HOME_CODE if home_score >= away_score else AWAY_CODE,
            position="MID",
            note="Controlled the midfield.",
        ),
        timeline=events,
        lineups=[_lineup(HOME_CODE, "Argentina"), _lineup(AWAY_CODE, "France")],
        footer_caption="Match data from the FIFA World Cup 2026.",
    )
