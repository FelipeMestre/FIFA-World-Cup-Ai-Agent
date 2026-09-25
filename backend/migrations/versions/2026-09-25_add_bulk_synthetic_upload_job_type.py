"""add bulk_synthetic_upload job type

Revision ID: d23ea2153231
Revises: 0f67254f34fc
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd23ea2153231'
down_revision: Union[str, Sequence[str], None] = '0f67254f34fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres allows ADD VALUE on an existing enum type inside a
    # transaction (PG12+) as long as the new value isn't used in the same
    # transaction -- this migration only adds it, a later one ingests with it.
    op.execute("ALTER TYPE ingestion_job_type ADD VALUE IF NOT EXISTS 'BULK_SYNTHETIC_UPLOAD'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no `ALTER TYPE ... DROP VALUE` -- removing an enum value
    # requires rebuilding the type (rename, recreate, cast, drop old, per
    # every other enum-altering migration in this project's history that
    # ever needed a real downgrade). Not implemented: no `ingestion_job` row
    # can reference this value if it was never used, and if it was used,
    # downgrading would orphan rows -- same tradeoff already accepted by
    # this migration set's other additive enum-value migrations.
    pass
