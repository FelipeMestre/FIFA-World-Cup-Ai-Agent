"""merge chat categorization and main migration heads

Revision ID: 0f67254f34fc
Revises: fc85c2fcda21, f1a7c3d5e9b2
Create Date: 2026-09-24 18:42:05.936218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f67254f34fc'
down_revision: Union[str, Sequence[str], None] = ('fc85c2fcda21', 'f1a7c3d5e9b2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
