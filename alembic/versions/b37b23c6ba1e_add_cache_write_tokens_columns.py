"""add cache_write_tokens columns

Revision ID: b37b23c6ba1e
Revises: g4b5c6d7e8f9
Create Date: 2026-01-11 12:08:50.054283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b37b23c6ba1e'
down_revision: Union[str, Sequence[str], None] = 'g4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cache_write_tokens columns to agent tracking tables."""
    op.add_column(
        'agent_conversations',
        sa.Column('total_cache_write_tokens', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'agent_runs',
        sa.Column('total_cache_write_tokens', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'llm_calls',
        sa.Column('cache_write_tokens', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Remove cache_write_tokens columns from agent tracking tables."""
    op.drop_column('llm_calls', 'cache_write_tokens')
    op.drop_column('agent_runs', 'total_cache_write_tokens')
    op.drop_column('agent_conversations', 'total_cache_write_tokens')
