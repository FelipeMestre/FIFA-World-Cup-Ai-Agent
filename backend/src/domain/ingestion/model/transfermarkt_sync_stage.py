"""Ordered checkpoint stages of a Transfermarkt sync pipeline run, used to
persist and expose which phase a running job is currently in. Values match
the `row_counts` keys `TransfermarktSyncService`/`TransfermarktDetailSync`
already use, so a stage and its row count line up under the same name.
"""

from enum import StrEnum


class TransfermarktSyncStage(StrEnum):
    NATIONAL_TEAMS = "national_teams"
    CLUBS = "clubs"
    PLAYERS = "players"
    PLAYER_VALUATIONS = "player_valuations"
    TRANSFERS = "transfers"
    GAME_LINEUPS = "game_lineups"
    GAME_EVENTS = "game_events"
    CLUB_GAMES = "club_games"
    SEASON_STATS = "real_player_season_stat"
