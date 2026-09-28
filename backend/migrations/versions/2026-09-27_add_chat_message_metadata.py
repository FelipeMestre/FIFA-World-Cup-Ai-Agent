"""add chat_message metadata

Revision ID: b3d6f1a29c47
Revises: d23ea2153231
Create Date: 2026-09-27 00:00:00.000000

Adds a nullable JSONB `metadata` column to `chat_message` -- server-resolved,
best-effort context pinned by the user for a turn (currently just the
match-selector chip's `{"match_selector": {...}}` shape), used to render a
badge on message replay/live events. Mapped in `ChatMessageSchema` as
`metadata_` (Python attribute), since `metadata` is reserved by
`DeclarativeBase`.

Chained onto `d23ea2153231` (one of two existing heads -- `3f9a675e70e1` is
the other, both enum-widening migrations unrelated to this one) rather than
merging them; this leaves the pre-existing multi-head state unresolved,
which is out of scope for this change.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b3d6f1a29c47"
down_revision: Union[str, Sequence[str], None] = "d23ea2153231"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_message",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_message", "metadata")
