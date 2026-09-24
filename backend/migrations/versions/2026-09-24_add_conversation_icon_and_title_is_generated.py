"""add conversation icon and title_is_generated

Revision ID: fc85c2fcda21
Revises: a4c8e2b91f03
Create Date: 2026-09-24 00:00:00.000000

Adds `icon` (nullable, app-level enum -- no DB check constraint) and
`title_is_generated` (defaults to true) to `conversation`. The
categorization background job sets both after generating a title/icon for
a new conversation; `title_is_generated` is flipped to false the moment a
user manually renames a conversation, so the job never clobbers a manual
rename (see `_SqlAlchemyConversationRepository.update_category`).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fc85c2fcda21"
down_revision: Union[str, Sequence[str], None] = "a4c8e2b91f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("icon", sa.Text(), nullable=True))
    op.add_column(
        "conversation",
        sa.Column(
            "title_is_generated", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("conversation", "title_is_generated")
    op.drop_column("conversation", "icon")
