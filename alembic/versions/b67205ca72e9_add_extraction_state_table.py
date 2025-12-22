"""add extraction_state table

Revision ID: b67205ca72e9
Revises: 1ca2fa8e2d82
Create Date: 2025-12-22 19:20:43.588742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b67205ca72e9'
down_revision: Union[str, Sequence[str], None] = '1ca2fa8e2d82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'extraction_state',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_id', sa.String(length=255), nullable=False),
        sa.Column('watermark', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id'),
    )
    op.create_index('idx_extraction_state_source_id', 'extraction_state', ['source_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_extraction_state_source_id', table_name='extraction_state')
    op.drop_table('extraction_state')
