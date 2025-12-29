"""Rename newsletters and articles tables to email_newsletters and email_articles

Revision ID: d1e2f3a4b5c6
Revises: c8f3a2d91e47
Create Date: 2025-12-29

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8f3a2d91e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename newsletters/articles tables to email_newsletters/email_articles."""
    # Drop existing indexes on articles table (need to recreate with new names)
    op.drop_index("idx_articles_newsletter_id", table_name="articles")
    op.drop_index("idx_articles_url_hash", table_name="articles")

    # Drop existing indexes on newsletters table
    op.drop_index("idx_newsletters_received_at", table_name="newsletters")
    op.drop_index("idx_newsletters_type", table_name="newsletters")

    # Rename tables
    op.rename_table("newsletters", "email_newsletters")
    op.rename_table("articles", "email_articles")

    # Recreate indexes with new names
    op.create_index(
        "idx_email_newsletters_received_at",
        "email_newsletters",
        ["received_at"],
        unique=False,
    )
    op.create_index(
        "idx_email_newsletters_type",
        "email_newsletters",
        ["newsletter_type"],
        unique=False,
    )
    op.create_index(
        "idx_email_articles_newsletter_id",
        "email_articles",
        ["newsletter_id"],
        unique=False,
    )
    op.create_index(
        "idx_email_articles_url_hash",
        "email_articles",
        ["url_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Revert table renames back to newsletters/articles."""
    # Drop new indexes
    op.drop_index("idx_email_articles_url_hash", table_name="email_articles")
    op.drop_index("idx_email_articles_newsletter_id", table_name="email_articles")
    op.drop_index("idx_email_newsletters_type", table_name="email_newsletters")
    op.drop_index("idx_email_newsletters_received_at", table_name="email_newsletters")

    # Rename tables back
    op.rename_table("email_articles", "articles")
    op.rename_table("email_newsletters", "newsletters")

    # Recreate original indexes
    op.create_index(
        "idx_newsletters_received_at",
        "newsletters",
        ["received_at"],
        unique=False,
    )
    op.create_index(
        "idx_newsletters_type",
        "newsletters",
        ["newsletter_type"],
        unique=False,
    )
    op.create_index(
        "idx_articles_newsletter_id",
        "articles",
        ["newsletter_id"],
        unique=False,
    )
    op.create_index(
        "idx_articles_url_hash",
        "articles",
        ["url_hash"],
        unique=False,
    )
