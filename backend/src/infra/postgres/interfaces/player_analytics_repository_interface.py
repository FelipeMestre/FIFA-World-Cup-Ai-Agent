"""Protocol for the player analytics repository used by the
`get_player_analysis`, `get_player_comparison`, and `query_player_stats`
chat tools.
"""

from typing import Protocol

from src.domain.player_analytics.model.player_analysis import PlayerAnalysis
from src.domain.player_analytics.model.player_comparison import PlayerComparison
from src.domain.player_analytics.model.player_ranking import PlayerRanking, QueryPlayerStatsRequest


class PlayerAnalyticsRepositoryInterface(Protocol):
    async def get_player_analysis(self, player_query: str) -> PlayerAnalysis | None:
        """Resolve `player_query` (a player name, case-insensitive, as supplied
        by the model from the user's message) against `player`, then aggregate
        that player's full tournament record -- stats, per-90s, position
        percentiles, and classification -- from `player_stat` and `player`.
        An approved `player_identity_link` also attaches the Transfermarkt
        club profile, a season-by-season club table, and the transfer path;
        pending and rejected links do not.

        Returns `None` when no player matches `player_query`; never raises
        for an unmatched query.
        """
        ...

    async def get_player_comparison(
        self, player_a_query: str, player_b_query: str
    ) -> PlayerComparison:
        """Resolve both `player_a_query` and `player_b_query` (case-insensitive
        names, as supplied by the model from the user's message) against
        `player`, then build a side-by-side per-90 comparison -- each stat's
        percentile computed within each player's own position peer group,
        since the two players may not share a position.

        Raises `PlayerNotFoundError` when either query fails to resolve, and
        `SamePlayerComparisonError` when both resolve to the same player.
        """
        ...

    async def query_player_stats(self, request: QueryPlayerStatsRequest) -> PlayerRanking:
        """Filter and sort squad players by allowlisted fields.

        `world_cup` reads `player_stat`. `club_seasons` sums approved-link
        `real_player_season_stat` rows inside the season window and
        competition filter. Returns an empty `rows` list when nothing
        matches; does not mix the two datasets.
        """
        ...
