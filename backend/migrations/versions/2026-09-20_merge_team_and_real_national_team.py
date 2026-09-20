"""merge team and real_national_team into national_team

Revision ID: a1c47f92d6e3
Revises: 8fe0872a186f
Create Date: 2026-09-20 00:00:02.000001

`team` (synthetic WC2026 dataset) and `real_national_team` (Transfermarkt)
described the same real-world entity from two sources, forcing two separate
joins to get one player's full national-team picture (`player.team_id` ->
`team`, and `real_player.current_national_team_id` -> `real_national_team`
via `player_identity_link` -> `real_player`). Merged into one
`national_team` table: `team_id` (the synthetic dataset's own id) stays the
primary key -- base rows only ever come from the synthetic WC2026 upload,
never from Transfermarkt -- and `real_national_team_id` becomes a plain
unique, nullable column instead of a second table. `real_player`'s FK now
points there directly, so both the synthetic and Transfermarkt paths to a
player's national team resolve to the same row.

`real_national_team.fifa_ranking` and `.coach_name` are NOT migrated:
`national_team.fifa_ranking_pre_tournament` and `.manager_name` (the
synthetic dataset's own values) are the ones the product uses -- see
`national_team_schema.py`'s docstring.

`upgrade()` doesn't attempt to migrate any existing `real_national_team`
rows into `national_team.real_national_team_id`: TransfermarktSyncService's
national_teams step now re-derives that match (by name, against the
synthetic `team_name`/`fifa_code`) and writes it on its next run, exactly
like a resume-mode-skipped step would. `downgrade()` can only reconstruct
`real_national_team` rows for teams that WERE matched/enriched by that
point -- a Transfermarkt country with no WC2026 match was never persisted
under the merged design and has no `national_team` row to recover it from.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c47f92d6e3'
down_revision: Union[str, Sequence[str], None] = '8fe0872a186f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE team RENAME TO national_team")
    op.execute("ALTER TABLE national_team RENAME CONSTRAINT team_pkey TO national_team_pkey")

    op.add_column('national_team', sa.Column('squad_size', sa.Integer(), nullable=True))
    op.add_column('national_team', sa.Column('average_age', sa.Numeric(4, 1), nullable=True))
    op.add_column(
        'national_team', sa.Column('total_market_value_eur', sa.Integer(), nullable=True)
    )
    op.add_column('national_team', sa.Column('url', sa.String(), nullable=True))

    op.drop_constraint('team_real_national_team_id_fkey', 'national_team', type_='foreignkey')
    op.drop_constraint(
        'real_player_current_national_team_id_fkey', 'real_player', type_='foreignkey'
    )
    op.drop_table('real_national_team')

    op.create_unique_constraint(
        op.f('national_team_real_national_team_id_key'),
        'national_team',
        ['real_national_team_id'],
    )
    op.create_foreign_key(
        op.f('real_player_current_national_team_id_fkey'),
        'real_player',
        'national_team',
        ['current_national_team_id'],
        ['real_national_team_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f('real_player_current_national_team_id_fkey'), 'real_player', type_='foreignkey'
    )

    op.create_table(
        'real_national_team',
        sa.Column('national_team_id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('country_name', sa.String(), nullable=False),
        sa.Column('confederation', sa.String(), nullable=False),
        sa.Column('fifa_ranking', sa.Integer(), nullable=True),
        sa.Column('squad_size', sa.Integer(), nullable=True),
        sa.Column('average_age', sa.Numeric(4, 1), nullable=True),
        sa.Column('total_market_value_eur', sa.Integer(), nullable=True),
        sa.Column('coach_name', sa.String(), nullable=True),
        sa.Column('url', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('national_team_id', name=op.f('real_national_team_pkey')),
    )
    # Best-effort reconstruction: only matched/enriched rows can come back,
    # and fifa_ranking/coach_name were never migrated forward in the first
    # place -- see this migration's module docstring.
    op.execute(
        "INSERT INTO real_national_team "
        "(national_team_id, name, country_name, confederation, squad_size, "
        "average_age, total_market_value_eur, url) "
        "SELECT real_national_team_id, team_name, team_name, confederation, "
        "squad_size, average_age, total_market_value_eur, "
        "COALESCE(url, 'https://example.invalid') "
        "FROM national_team WHERE real_national_team_id IS NOT NULL"
    )

    op.drop_constraint(
        op.f('national_team_real_national_team_id_key'), 'national_team', type_='unique'
    )
    op.drop_column('national_team', 'url')
    op.drop_column('national_team', 'total_market_value_eur')
    op.drop_column('national_team', 'average_age')
    op.drop_column('national_team', 'squad_size')

    op.execute("ALTER TABLE national_team RENAME CONSTRAINT national_team_pkey TO team_pkey")
    op.execute("ALTER TABLE national_team RENAME TO team")

    op.create_foreign_key(
        op.f('team_real_national_team_id_fkey'),
        'team',
        'real_national_team',
        ['real_national_team_id'],
        ['national_team_id'],
    )
    op.create_foreign_key(
        op.f('real_player_current_national_team_id_fkey'),
        'real_player',
        'real_national_team',
        ['current_national_team_id'],
        ['national_team_id'],
    )
