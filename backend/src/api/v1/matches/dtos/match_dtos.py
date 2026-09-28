from datetime import date, time

from pydantic import BaseModel

from src.domain.matches.model.match import Match, MatchSearchRow


class MatchResponse(BaseModel):
    id: int
    date: date
    kickoff_time_utc: time
    stage_id: int
    venue_id: int
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    home_penalty_score: int | None
    away_penalty_score: int | None
    status: str
    result_type: str
    home_xg: float
    away_xg: float
    referee_id: int
    player_of_the_match_id: int

    @classmethod
    def from_domain(cls, match: Match) -> "MatchResponse":
        return cls(
            id=match.id,
            date=match.date,
            kickoff_time_utc=match.kickoff_time_utc,
            stage_id=match.stage_id,
            venue_id=match.venue_id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            home_score=match.home_score,
            away_score=match.away_score,
            home_penalty_score=match.home_penalty_score,
            away_penalty_score=match.away_penalty_score,
            status=match.status,
            result_type=match.result_type,
            home_xg=match.home_xg,
            away_xg=match.away_xg,
            referee_id=match.referee_id,
            player_of_the_match_id=match.player_of_the_match_id,
        )


class MatchSearchResultDto(BaseModel):
    """One `GET /matches/search` result -- carries team names (unlike
    `MatchResponse`, which only has ids) so the match-selector chip can
    render a label like "Brazil vs Argentina" without a follow-up lookup.
    """

    id: int
    date: date
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_score: int
    away_score: int
    status: str

    @classmethod
    def from_domain(cls, row: MatchSearchRow) -> "MatchSearchResultDto":
        return cls(
            id=row.match.id,
            date=row.match.date,
            home_team_id=row.match.home_team_id,
            home_team_name=row.home_team_name,
            away_team_id=row.match.away_team_id,
            away_team_name=row.away_team_name,
            home_score=row.match.home_score,
            away_score=row.match.away_score,
            status=row.match.status,
        )
