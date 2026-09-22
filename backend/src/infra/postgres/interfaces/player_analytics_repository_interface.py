"""Protocol for the player analytics repository used by the
`get_player_analysis` chat tool.
"""

from typing import Protocol

from src.domain.player_analytics.model.player_analysis import PlayerAnalysis


class PlayerAnalyticsRepositoryInterface(Protocol):
    async def get_player_analysis(self, player_query: str) -> PlayerAnalysis | None:
        """Resolve `player_query` (a player name, case-insensitive, as supplied
        by the model from the user's message) against `player`, then aggregate
        that player's full tournament record -- stats, per-90s, position
        percentiles, and classification -- from `player_stat`, `match_event`,
        `match_lineup`, and `player`.

        Returns `None` when no player matches `player_query`; never raises
        for an unmatched query.
        """
        ...
