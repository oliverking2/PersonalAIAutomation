"""Add selected_domains to agent_conversations

Revision ID: 2a3b4c5d6e7f
Revises: 1e15f73f876a
Create Date: 2026-01-19 19:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '2a3b4c5d6e7f'
down_revision: Union[str, Sequence[str], None] = '1e15f73f876a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add selected_domains column to agent_conversations table."""
    op.add_column(
        'agent_conversations',
        sa.Column('selected_domains', JSONB, nullable=True)
    )


def downgrade() -> None:
    """Remove selected_domains column from agent_conversations table."""
    op.drop_column('agent_conversations', 'selected_domains')
