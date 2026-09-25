from typing import Protocol

from src.domain.team_analytics.model.team_analysis import TeamAnalysis
from src.domain.team_analytics.model.team_comparison import TeamComparison


class TeamAnalyticsRepositoryInterface(Protocol):
    async def get_team_analysis(self, team_query: str) -> TeamAnalysis | None:
        """Resolve `team_query` (a team name or FIFA code, case-insensitive,
        as supplied by the model from the user's message) against
        `national_team`, then aggregate that team's full tournament record
        -- results, goals, tournament-wide stat comparisons, World Cup squad
        identity and position groups, and discipline
        -- from `match`, `match_team_stat`, `match_event`, and `player`.

        Returns `None` when no team matches `team_query`; never raises for
        an unmatched query.
        """
        ...

    async def get_team_comparison(self, team_a_query: str, team_b_query: str) -> TeamComparison:
        """Resolve both queries the same way as `get_team_analysis`, then
        build the head-to-head read model.

        Raises `TeamNotFoundError` when either query matches no team, and
        `SameTeamComparisonError` when both resolve to the same team.
        """
        ...
