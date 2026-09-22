"""Protocol for the match analytics repository used by the
`get_match_analysis` chat tool.
"""

from typing import Protocol

from src.domain.match_analytics.model.match_analysis import (
    MatchAnalysis,
    MatchAnalysisAmbiguous,
)


class MatchAnalyticsRepositoryInterface(Protocol):
    async def get_match_analysis(
        self,
        home_team_query: str,
        away_team_query: str,
        stage: str | None = None,
        date: str | None = None,
    ) -> MatchAnalysis | MatchAnalysisAmbiguous | None:
        """Resolve `home_team_query`/`away_team_query` (team names or FIFA
        codes, case-insensitive, as supplied by the model from the user's
        message) against `national_team` the same way
        `TeamAnalyticsRepositoryInterface.get_team_analysis` resolves one
        name, then look up the match between them -- optionally narrowed by
        `stage` (fuzzy match against `tournament_stage.stage_name`) and/or
        `date` (an ISO `YYYY-MM-DD` string matched against `match.date`) when
        the two teams played each other more than once.

        Returns `None` when either team can't be resolved or no match
        between them (matching any given `stage`/`date`) exists.
        Returns `MatchAnalysisAmbiguous` when more than one match matches.
        Never raises for an unmatched or ambiguous query.
        """
        ...
