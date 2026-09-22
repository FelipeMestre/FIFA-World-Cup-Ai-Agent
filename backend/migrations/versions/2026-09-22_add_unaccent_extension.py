"""add unaccent extension

Revision ID: 5d0e3a7c19f4
Revises: c47e91b3a5d8
Create Date: 2026-09-22 00:00:00.000001

`_resolve_player` in `player_analytics_repository.py` matched player names
via plain `ILIKE`, so an accented query (e.g. "Mbappé") failed to match the
DB's unaccented stored name ("Kylian Mbappe"). This migration installs
Postgres's built-in `unaccent` extension so the repository can wrap both
sides of the `ILIKE` comparison in `func.unaccent(...)` for
diacritic-insensitive matching.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5d0e3a7c19f4'
down_revision: Union[str, Sequence[str], None] = 'c47e91b3a5d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS unaccent;")
