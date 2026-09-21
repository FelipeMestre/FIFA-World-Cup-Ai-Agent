from typing import Protocol

from src.domain.team_analytics.model.team_analysis import TeamAnalysis


class TeamAnalyticsRepositoryInterface(Protocol):
    async def get_team_analysis(self, team_query: str) -> TeamAnalysis | None:
        """Resolve `team_query` (a team name or FIFA code, case-insensitive,
        as supplied by the model from the user's message) against
        `national_team`, then aggregate that team's full tournament record
        -- results, goals, tournament-wide stat comparisons, and discipline
        -- from `match`, `match_team_stat`, and `match_event`.

        Returns `None` when no team matches `team_query`; never raises for
        an unmatched query.
        """
        ...
