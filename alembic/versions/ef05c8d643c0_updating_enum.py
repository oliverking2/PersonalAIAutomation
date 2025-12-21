"""Updating enum

Revision ID: ef05c8d643c0
Revises: 3453c4fca5d9
Create Date: 2025-12-21 17:37:26.465387

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef05c8d643c0'
down_revision: Union[str, Sequence[str], None] = '3453c4fca5d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum value if it does not already exist
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_enum
            WHERE enumlabel = 'TLDR_DATA'
              AND enumtypid = 'newsletter_type_enum'::regtype
        ) THEN
            ALTER TYPE newsletter_type_enum ADD VALUE 'TLDR_DATA';
        END IF;
    END
    $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # enums cannot be removed, so no need to downgrade
    pass
