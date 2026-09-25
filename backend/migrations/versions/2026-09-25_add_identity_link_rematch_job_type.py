"""add identity link rematch job type

Revision ID: 3f9a675e70e1
Revises: 0f67254f34fc
Create Date: 2026-09-25 11:54:28.771427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f9a675e70e1'
down_revision: Union[str, Sequence[str], None] = '0f67254f34fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The label must be the Python enum member's NAME (uppercase), not its
    # `.value` -- SQLAlchemy's Enum column type stores by member name by
    # default (confirmed against this same table's existing
    # 'SYNTHETIC_UPLOAD'/'TRANSFERMARKT_SYNC' labels, added by the original
    # sa.Enum('SYNTHETIC_UPLOAD', 'TRANSFERMARKT_SYNC', ...) call in
    # 2026-09-19_add_real_match_tables_and_ingestion_job.py -- verified live:
    # inserting the lowercase `.value` string raises
    # InvalidTextRepresentationError, not a silent no-op).
    #
    # New value is not usable inside this same transaction, only after it
    # commits -- fine here, since nothing in this migration inserts a row
    # using it.
    op.execute("ALTER TYPE ingestion_job_type ADD VALUE 'IDENTITY_LINK_REMATCH'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no ALTER TYPE ... DROP VALUE -- removing an enum value
    # requires recreating the type and every column/index that uses it.
    # Left as a irreversible additive change, same as this codebase's other
    # enum-widening migrations with no downgrade path.
    pass
