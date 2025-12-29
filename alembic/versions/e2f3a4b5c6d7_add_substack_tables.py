"""Add substack_newsletters and substack_posts tables

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2025-12-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create substack_newsletters and substack_posts tables."""
    # Create substack_newsletters table
    op.create_table(
        "substack_newsletters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_substack_newsletters_url"),
    )
    op.create_index(
        "idx_substack_newsletters_url",
        "substack_newsletters",
        ["url"],
        unique=False,
    )

    # Create substack_posts table
    op.create_table(
        "substack_posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("newsletter_id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("subtitle", sa.String(length=1000), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("is_paywalled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["newsletter_id"],
            ["substack_newsletters.id"],
            name="fk_substack_posts_newsletter_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", name="uq_substack_posts_post_id"),
    )
    op.create_index(
        "idx_substack_posts_newsletter_id",
        "substack_posts",
        ["newsletter_id"],
        unique=False,
    )
    op.create_index(
        "idx_substack_posts_published_at",
        "substack_posts",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        "idx_substack_posts_alerted_at",
        "substack_posts",
        ["alerted_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop substack tables."""
    op.drop_index("idx_substack_posts_alerted_at", table_name="substack_posts")
    op.drop_index("idx_substack_posts_published_at", table_name="substack_posts")
    op.drop_index("idx_substack_posts_newsletter_id", table_name="substack_posts")
    op.drop_table("substack_posts")

    op.drop_index("idx_substack_newsletters_url", table_name="substack_newsletters")
    op.drop_table("substack_newsletters")
