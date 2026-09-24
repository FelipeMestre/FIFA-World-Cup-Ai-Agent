"""add real_player full_name search index

Revision ID: cbba0641a6b0
Revises: a4c8e2b91f03
Create Date: 2026-09-24 00:00:00.000000

`RealPlayerRepository.search` (backing the admin identity-link "correct
match" picker) does an `ILIKE '%query%'` substring match over player names.
Unindexed, that's a sequential scan across every `real_player` row on every
keystroke -- fine at today's row count, not once a full Transfermarkt sync
populates the table with its full player universe (tens of thousands of
rows, per the ingestion change that stopped filtering `real_player` down to
only WC2026-matched players).

Adds `full_name`, a Postgres-maintained `GENERATED ALWAYS ... STORED` column
(never set by application code, so it can't drift from
first_name/last_name), and a `pg_trgm` GIN index on it so the ILIKE query
can use an index (bitmap) scan instead of a seq scan. The repository's query
was updated to filter on this column directly rather than a query-time
`first_name || ' ' || last_name` concatenation -- Postgres only matches an
expression index against a byte-identical query expression, and a
parameterized query's bind variable for the separator would silently defeat
that match, leaving the index built but unused.

Adding a GENERATED column rewrites the table to backfill every existing row
(an ACCESS EXCLUSIVE lock for the duration) -- acceptable here given the
table's current size and that this isn't a hot path under concurrent writes.

Verified against a live 50k-row table: the planner falls back to a seq scan
for very short queries (2-4 chars, where pg_trgm's few trigrams don't narrow
candidates much) but correctly picks the index for realistic admin input
(5+ characters) -- roughly 150x fewer buffer reads and 150x faster.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cbba0641a6b0"
down_revision: Union[str, Sequence[str], None] = "a4c8e2b91f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute(
        "ALTER TABLE real_player "
        "ADD COLUMN full_name text "
        "GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED NOT NULL;"
    )
    op.execute(
        "CREATE INDEX real_player_full_name_idx "
        "ON real_player USING gin (full_name gin_trgm_ops);"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS real_player_full_name_idx;")
    op.execute("ALTER TABLE real_player DROP COLUMN IF EXISTS full_name;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
