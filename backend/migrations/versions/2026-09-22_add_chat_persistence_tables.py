"""add chat persistence tables

Revision ID: 9c2f6a1d84b7
Revises: 5d0e3a7c19f4
Create Date: 2026-09-22 00:00:00.000002

Moves chat conversation history from Redis-only (TTL-bound, lossy) to a
durable Postgres append-only log as source of truth, with Redis kept as a
read-through cache. `conversation.id` is client-generated (no server-side
default) so it can be pushed into the URL before the first message is
sent. `chat_message` is append-only -- never UPDATEd by application code.
`chat_message_widget` is kept separate from `chat_message.content` to
protect LLM prompt-cache stability.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9c2f6a1d84b7'
down_revision: Union[str, Sequence[str], None] = '5d0e3a7c19f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('conversation',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('conversation_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('conversation_pkey'))
    )
    op.create_index(op.f('conversation_user_id_idx'), 'conversation', ['user_id'], unique=False)
    op.create_table('chat_message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('role', sa.Enum('USER', 'ASSISTANT', name='chat_message_role'), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], name=op.f('chat_message_conversation_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('chat_message_pkey')),
    sa.UniqueConstraint('conversation_id', 'sequence', name=op.f('chat_message_conversation_id_key'))
    )
    op.create_index(op.f('chat_message_conversation_id_idx'), 'chat_message', ['conversation_id'], unique=False)
    op.create_table('chat_message_widget',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('tool_name', sa.String(), nullable=False),
    sa.Column('widget_type', sa.String(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['chat_message.id'], name=op.f('chat_message_widget_message_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('chat_message_widget_pkey'))
    )
    op.create_index(op.f('chat_message_widget_message_id_idx'), 'chat_message_widget', ['message_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('chat_message_widget_message_id_idx'), table_name='chat_message_widget')
    op.drop_table('chat_message_widget')
    op.drop_index(op.f('chat_message_conversation_id_idx'), table_name='chat_message')
    op.drop_table('chat_message')
    postgresql.ENUM(name='chat_message_role').drop(op.get_bind())
    op.drop_index(op.f('conversation_user_id_idx'), table_name='conversation')
    op.drop_table('conversation')
