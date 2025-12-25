"""rename conversations and make agent_run_id nullable

Revision ID: e7212fb5ba96
Revises: 03cc9dfa944e
Create Date: 2025-12-25 19:46:49.852795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7212fb5ba96'
down_revision: Union[str, Sequence[str], None] = '03cc9dfa944e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename conversations table to agent_conversations
    op.rename_table('conversations', 'agent_conversations')

    # Update indexes with new names
    op.drop_index('idx_conversations_external_id', table_name='agent_conversations')
    op.drop_index('idx_conversations_started_at', table_name='agent_conversations')
    op.create_index(
        'idx_agent_conversations_external_id',
        'agent_conversations',
        ['external_id'],
        unique=False,
    )
    op.create_index(
        'idx_agent_conversations_started_at',
        'agent_conversations',
        ['started_at'],
        unique=False,
    )

    # Update foreign key in agent_runs to reference new table name
    op.drop_constraint('agent_runs_conversation_id_fkey', 'agent_runs', type_='foreignkey')
    op.create_foreign_key(
        'agent_runs_conversation_id_fkey',
        'agent_runs',
        'agent_conversations',
        ['conversation_id'],
        ['id'],
    )

    # Make agent_run_id nullable in llm_calls
    op.alter_column(
        'llm_calls',
        'agent_run_id',
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Make agent_run_id non-nullable again
    op.alter_column(
        'llm_calls',
        'agent_run_id',
        existing_type=sa.UUID(),
        nullable=False,
    )

    # Restore foreign key to old table name
    op.drop_constraint('agent_runs_conversation_id_fkey', 'agent_runs', type_='foreignkey')
    op.create_foreign_key(
        'agent_runs_conversation_id_fkey',
        'agent_runs',
        'conversations',
        ['conversation_id'],
        ['id'],
    )

    # Restore old index names
    op.drop_index('idx_agent_conversations_external_id', table_name='agent_conversations')
    op.drop_index('idx_agent_conversations_started_at', table_name='agent_conversations')
    op.create_index(
        'idx_conversations_external_id',
        'agent_conversations',
        ['external_id'],
        unique=False,
    )
    op.create_index(
        'idx_conversations_started_at',
        'agent_conversations',
        ['started_at'],
        unique=False,
    )

    # Rename table back
    op.rename_table('agent_conversations', 'conversations')
