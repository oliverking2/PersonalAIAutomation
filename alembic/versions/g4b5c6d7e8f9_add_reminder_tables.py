"""Add reminder tables

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2025-01-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create reminder_schedules table
    op.create_table(
        "reminder_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("cron_schedule", sa.String(length=100), nullable=True),
        sa.Column("next_trigger_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_reminder_schedules_next_trigger",
        "reminder_schedules",
        ["next_trigger_at", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_reminder_schedules_chat_id",
        "reminder_schedules",
        ["chat_id"],
        unique=False,
    )

    # Create reminder_instances table
    op.create_table(
        "reminder_instances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_sends", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["reminder_schedules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_reminder_instances_status_next_send",
        "reminder_instances",
        ["status", "next_send_at"],
        unique=False,
    )
    op.create_index(
        "idx_reminder_instances_schedule_id",
        "reminder_instances",
        ["schedule_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_reminder_instances_schedule_id", table_name="reminder_instances")
    op.drop_index("idx_reminder_instances_status_next_send", table_name="reminder_instances")
    op.drop_table("reminder_instances")
    op.drop_index("idx_reminder_schedules_chat_id", table_name="reminder_schedules")
    op.drop_index("idx_reminder_schedules_next_trigger", table_name="reminder_schedules")
    op.drop_table("reminder_schedules")
