"""add user name

Revision ID: a4c8e2b91f03
Revises: 605612c84d08
Create Date: 2026-09-23 23:21:00.000000

Adds a required display name on `user`. Existing rows are backfilled from
the local part of `email` (or `'User'` if that local part is empty / too
long) so the column can be NOT NULL without a server default.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a4c8e2b91f03"
down_revision: Union[str, Sequence[str], None] = "605612c84d08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("name", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            'UPDATE "user" SET name = CASE '
            "WHEN char_length(btrim(split_part(email, '@', 1))) BETWEEN 1 AND 128 "
            "THEN split_part(email, '@', 1) "
            "ELSE 'User' END "
            "WHERE name IS NULL"
        )
    )
    op.alter_column("user", "name", existing_type=sa.Text(), nullable=False)
    op.execute(
        sa.text(
            'ALTER TABLE "user" ADD CONSTRAINT user_name_not_blank_check '
            "CHECK (char_length(btrim(name)) BETWEEN 1 AND 128)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text('ALTER TABLE "user" DROP CONSTRAINT user_name_not_blank_check'))
    op.drop_column("user", "name")
