"""widen real_game_lineup/real_match_event id columns from integer to text

Revision ID: 8fe0872a186f
Revises: 8f3a1c9d2b47
Create Date: 2026-09-20 00:00:00.000001

Verified against the live Transfermarkt source: `game_lineups.csv`'s
`game_lineups_id` and `game_events.csv`'s `game_event_id` are 32-character
hex hash strings (e.g. "b2dbe01c3656b06c8e23e9de714e26bb"), not integers.
`real_game_lineup.game_lineups_id` / `real_match_event.game_event_id` were
created as INTEGER primary keys -- a design assumption made without
checking the real export's value format, only its column names. A real
sync run hit `invalid literal for int()` the moment ingestion reached
`game_lineups.csv`.

`upgrade()` needs no data conversion, since no prior run had successfully
populated these tables when this migration was first written. `downgrade()`
truncates both tables first: a hash-string id has no valid integer
representation, so reverting to the old INTEGER columns cannot preserve
whatever real (hash-string) rows a later successful run may have written --
those rows would need to be re-ingested after a downgrade regardless.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8fe0872a186f'
down_revision: Union[str, Sequence[str], None] = '8f3a1c9d2b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE real_game_lineup ALTER COLUMN game_lineups_id TYPE VARCHAR "
        "USING game_lineups_id::VARCHAR"
    )
    op.execute(
        "ALTER TABLE real_match_event ALTER COLUMN game_event_id TYPE VARCHAR "
        "USING game_event_id::VARCHAR"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # No valid int representation exists for a hash-string id -- truncate
    # rather than attempt a lossy/failing cast.
    op.execute("TRUNCATE TABLE real_match_event")
    op.execute("TRUNCATE TABLE real_game_lineup")
    op.execute(
        "ALTER TABLE real_match_event ALTER COLUMN game_event_id TYPE INTEGER "
        "USING game_event_id::INTEGER"
    )
    op.execute(
        "ALTER TABLE real_game_lineup ALTER COLUMN game_lineups_id TYPE INTEGER "
        "USING game_lineups_id::INTEGER"
    )
