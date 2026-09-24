"""add chat turn failure table

Revision ID: 605612c84d08
Revises: 9c2f6a1d84b7
Create Date: 2026-09-23 22:24:29.513296

Marks that generation failed for a given `chat_message`, kept in its own
table (never in `chat_message`/`chat_message_widget`) so a failed turn is
never sent back to the LLM as conversation history when reconstructing the
prompt. `user_message_id` is unique -- a retry always creates a new
`chat_message` row rather than reusing this one.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '605612c84d08'
down_revision: Union[str, Sequence[str], None] = '9c2f6a1d84b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('chat_turn_failure',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('user_message_id', sa.Integer(), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], name=op.f('chat_turn_failure_conversation_id_fkey')),
    sa.ForeignKeyConstraint(['user_message_id'], ['chat_message.id'], name=op.f('chat_turn_failure_user_message_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('chat_turn_failure_pkey')),
    sa.UniqueConstraint('user_message_id', name=op.f('chat_turn_failure_user_message_id_key'))
    )
    op.create_index(op.f('chat_turn_failure_conversation_id_idx'), 'chat_turn_failure', ['conversation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('chat_turn_failure_conversation_id_idx'), table_name='chat_turn_failure')
    op.drop_table('chat_turn_failure')
