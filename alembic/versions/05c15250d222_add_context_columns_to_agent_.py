"""add_context_columns_to_agent_conversations

Revision ID: 05c15250d222
Revises: e7212fb5ba96
Create Date: 2025-12-25 20:38:43.437284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '05c15250d222'
down_revision: Union[str, Sequence[str], None] = 'e7212fb5ba96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add context management columns to agent_conversations."""
    # Message history (recent messages in Bedrock format)
    op.add_column(
        'agent_conversations',
        sa.Column('messages_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Currently selected tool names for the conversation
    op.add_column(
        'agent_conversations',
        sa.Column('selected_tools', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Pending confirmation details (tool_use_id, tool_name, input_args, etc.)
    op.add_column(
        'agent_conversations',
        sa.Column('pending_confirmation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Rolling summary of older messages
    op.add_column(
        'agent_conversations',
        sa.Column('summary', sa.Text(), nullable=True),
    )

    # Total message count in conversation
    op.add_column(
        'agent_conversations',
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
    )

    # When summary was last updated
    op.add_column(
        'agent_conversations',
        sa.Column('last_summarised_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove context management columns from agent_conversations."""
    op.drop_column('agent_conversations', 'last_summarised_at')
    op.drop_column('agent_conversations', 'message_count')
    op.drop_column('agent_conversations', 'summary')
    op.drop_column('agent_conversations', 'pending_confirmation')
    op.drop_column('agent_conversations', 'selected_tools')
    op.drop_column('agent_conversations', 'messages_json')
