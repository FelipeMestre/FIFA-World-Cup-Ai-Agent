"""merge job type and chat metadata heads

Revision ID: 33e53bae72d2
Revises: 3f9a675e70e1, b3d6f1a29c47
Create Date: 2026-09-30 12:06:18.932353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33e53bae72d2'
down_revision: Union[str, Sequence[str], None] = ('3f9a675e70e1', 'b3d6f1a29c47')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
