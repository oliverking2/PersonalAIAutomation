"""Add alerted_at to newsletters

Revision ID: a1b2c3d4e5f6
Revises: ef05c8d643c0
Create Date: 2025-12-21 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "ef05c8d643c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add alerted_at column to newsletters table."""
    op.add_column(
        "newsletters",
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove alerted_at column from newsletters table."""
    op.drop_column("newsletters", "alerted_at")
