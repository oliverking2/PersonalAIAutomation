"""Add sent_alerts table

Revision ID: c8f3a2d91e47
Revises: 2b07155adfe9
Create Date: 2025-12-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f3a2d91e47"
down_revision: Union[str, Sequence[str], None] = "2b07155adfe9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create sent_alerts table
    op.create_table(
        "sent_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "alert_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_sent_alerts_type_sent_at",
        "sent_alerts",
        ["alert_type", "sent_at"],
        unique=False,
    )
    op.create_index(
        "idx_sent_alerts_source_id",
        "sent_alerts",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_sent_alerts_source_id", table_name="sent_alerts")
    op.drop_index("idx_sent_alerts_type_sent_at", table_name="sent_alerts")
    op.drop_table("sent_alerts")
