"""Add medium_digests and medium_articles tables

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-01-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create medium_digests and medium_articles tables."""
    # Create medium_digests table
    op.create_table(
        "medium_digests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email_id", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_id", name="uq_medium_digests_email_id"),
    )
    op.create_index(
        "idx_medium_digests_received_at",
        "medium_digests",
        ["received_at"],
        unique=False,
    )

    # Create medium_articles table
    op.create_table(
        "medium_articles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("digest_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("read_time_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["medium_digests.id"],
            name="fk_medium_articles_digest_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_medium_articles_digest_id",
        "medium_articles",
        ["digest_id"],
        unique=False,
    )
    op.create_index(
        "idx_medium_articles_url_hash",
        "medium_articles",
        ["url_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Drop medium tables."""
    op.drop_index("idx_medium_articles_url_hash", table_name="medium_articles")
    op.drop_index("idx_medium_articles_digest_id", table_name="medium_articles")
    op.drop_table("medium_articles")

    op.drop_index("idx_medium_digests_received_at", table_name="medium_digests")
    op.drop_table("medium_digests")
