"""add unique constraints for transfermarkt detail upsert natural keys

Revision ID: 8f3a1c9d2b47
Revises: 14ba028c3574
Create Date: 2026-09-20 00:00:00.000000

`real_player_valuation` and `real_transfer` were created with only a
surrogate `id` primary key (see `real_player_schema.py`'s own docstrings).
`TRANSFERMARKT_DETAIL_SPECS` (PR 3) declares `conflict_columns=
("real_player_id", "valuation_date")` / `("real_player_id",
"transfer_date")` for their `ON CONFLICT DO UPDATE` upserts, but Postgres
requires a matching unique/exclusion constraint for `ON CONFLICT` to target
-- neither table had one. This migration adds exactly the constraints those
specs need so PR 4's `TransfermarktDetailSync` can actually upsert into
these two tables.

Any pre-existing same-natural-key duplicate rows are collapsed to the most
recent `id` before the constraint is added, since a `UNIQUE` constraint
cannot be created over data that already violates it. This is consistent
with the rest of the ingestion pipeline's natural-key upsert idempotency
model: a later run overwrites an earlier one for the same key rather than
accumulating duplicates.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8f3a1c9d2b47'
down_revision: Union[str, Sequence[str], None] = '14ba028c3574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DELETE FROM real_player_valuation a
        USING real_player_valuation b
        WHERE a.id < b.id
          AND a.real_player_id = b.real_player_id
          AND a.valuation_date = b.valuation_date
        """
    )
    op.execute(
        """
        DELETE FROM real_transfer a
        USING real_transfer b
        WHERE a.id < b.id
          AND a.real_player_id = b.real_player_id
          AND a.transfer_date = b.transfer_date
        """
    )
    op.create_unique_constraint(
        op.f('real_player_valuation_real_player_id_key'),
        'real_player_valuation',
        ['real_player_id', 'valuation_date'],
    )
    op.create_unique_constraint(
        op.f('real_transfer_real_player_id_key'),
        'real_transfer',
        ['real_player_id', 'transfer_date'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f('real_transfer_real_player_id_key'), 'real_transfer', type_='unique'
    )
    op.drop_constraint(
        op.f('real_player_valuation_real_player_id_key'),
        'real_player_valuation',
        type_='unique',
    )
