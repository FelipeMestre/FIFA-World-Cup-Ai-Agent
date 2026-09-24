"""add ingestion_job stage tracking

Revision ID: f1a7c3d5e9b2
Revises: cbba0641a6b0
Create Date: 2026-09-24 00:00:00.000000

Adds `current_stage` (the Transfermarkt sync pipeline phase a `running` job
is currently on, e.g. "players", "game_lineups") and `stage_checkpoints` (an
append-only JSONB history of `{stage, completed_at}` entries) to
`ingestion_job`. Lets `GET /admin/ingestion/jobs/{job_id}` report live
progress through the pipeline instead of only queued/running/succeeded/
failed -- a `synthetic_upload` job simply never writes these columns, so
they stay null/empty for it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "f1a7c3d5e9b2"
down_revision: Union[str, Sequence[str], None] = "cbba0641a6b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("ingestion_job", sa.Column("current_stage", sa.String(), nullable=True))
    op.add_column(
        "ingestion_job",
        sa.Column(
            "stage_checkpoints",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ingestion_job", "stage_checkpoints")
    op.drop_column("ingestion_job", "current_stage")
