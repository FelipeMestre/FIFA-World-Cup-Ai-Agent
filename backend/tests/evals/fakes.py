"""Fake repositories for the grounding evals.

Only repositories are faked; the real handlers, registry and executor run.
Two families exist:

- Configurable fakes (`FakeTeamAnalyticsRepository` and friends) serve fixed
  outcomes. A method with no configured outcome behaves like an empty
  database (`None`, no rows, or the domain "not found" error), exactly what a
  real repository returns for an unmatched query.
- `Unused*` repositories raise `NotImplementedError` on every call. The
  executor does not catch handler exceptions, so an unexpected tool call
  aborts the test loudly instead of silently passing.

Every fake records the repository methods it served in `calls`.
"""

from src.domain.chat.exceptions.chat_exceptions import PlayerNotFoundError, TeamNotFoundError
from src.domain.match_analytics.model.match_analysis import (
    MatchAnalysis,
    MatchAnalysisAmbiguous,
)
from src.domain.player_analytics.model.player_analysis import PlayerAnalysis
from src.domain.player_analytics.model.player_comparison import PlayerComparison
from src.domain.player_analytics.model.player_ranking import (
    PlayerRanking,
    QueryPlayerStatsRequest,
)
from src.domain.team_analytics.model.team_analysis import TeamAnalysis
from src.domain.team_analytics.model.team_comparison import TeamComparison

NO_RANKING_ROWS_ID = "empty-ranking"


class _RecordingRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []


def _serve[T](outcome: T | Exception) -> T:
    """Return the outcome, or raise it when it is a domain error."""
    if isinstance(outcome, Exception):
        raise outcome
    return outcome


class FakeTeamAnalyticsRepository(_RecordingRepository):
    def __init__(
        self,
        analysis: TeamAnalysis | None = None,
        comparison: TeamComparison | Exception | None = None,
    ) -> None:
        super().__init__()
        self._analysis = analysis
        self._comparison = comparison

    async def get_team_analysis(self, team_query: str) -> TeamAnalysis | None:
        self.calls.append("get_team_analysis")
        return self._analysis

    async def get_team_comparison(self, team_a_query: str, team_b_query: str) -> TeamComparison:
        self.calls.append("get_team_comparison")
        if self._comparison is None:
            raise TeamNotFoundError(f"No team found matching '{team_a_query}'.")
        return _serve(self._comparison)


class FakePlayerAnalyticsRepository(_RecordingRepository):
    def __init__(
        self,
        analysis: PlayerAnalysis | None = None,
        comparison: PlayerComparison | Exception | None = None,
        ranking: PlayerRanking | None = None,
    ) -> None:
        super().__init__()
        self._analysis = analysis
        self._comparison = comparison
        self._ranking = ranking

    async def get_player_analysis(self, player_query: str) -> PlayerAnalysis | None:
        self.calls.append("get_player_analysis")
        return self._analysis

    async def get_player_comparison(
        self, player_a_query: str, player_b_query: str
    ) -> PlayerComparison:
        self.calls.append("get_player_comparison")
        if self._comparison is None:
            raise PlayerNotFoundError(f"No player found matching '{player_a_query}'.")
        return _serve(self._comparison)

    async def query_player_stats(self, request: QueryPlayerStatsRequest) -> PlayerRanking:
        self.calls.append("query_player_stats")
        if self._ranking is None:
            return PlayerRanking(
                id=NO_RANKING_ROWS_ID,
                scope="world_cup",
                rank_by=request.sort_by.value,
                rank_by_label=request.sort_by.value,
                scope_label="FIFA World Cup 2026",
                footer_caption="",
                rows=[],
            )
        return self._ranking


class FakeMatchAnalyticsRepository(_RecordingRepository):
    def __init__(self, result: MatchAnalysis | MatchAnalysisAmbiguous | None = None) -> None:
        super().__init__()
        self._result = result

    async def get_match_analysis(
        self,
        home_team_query: str,
        away_team_query: str,
        stage: str | None = None,
        date: str | None = None,
    ) -> MatchAnalysis | MatchAnalysisAmbiguous | None:
        self.calls.append("get_match_analysis")
        return self._result


class UnusedTeamRepository(_RecordingRepository):
    async def get_team_analysis(self, team_query: str):
        raise NotImplementedError("team analysis is out of scope for this eval")

    async def get_team_comparison(self, team_a_query: str, team_b_query: str):
        raise NotImplementedError("team comparison is out of scope for this eval")


class UnusedPlayerRepository(_RecordingRepository):
    async def get_player_analysis(self, player_query: str):
        raise NotImplementedError("player analysis is out of scope for this eval")

    async def get_player_comparison(self, player_a_query: str, player_b_query: str):
        raise NotImplementedError("player comparison is out of scope for this eval")

    async def query_player_stats(self, request):
        raise NotImplementedError("player ranking is out of scope for this eval")


class UnusedMatchRepository(_RecordingRepository):
    async def get_match_analysis(self, home_team_query, away_team_query, stage=None, date=None):
        raise NotImplementedError("match analysis is out of scope for this eval")
