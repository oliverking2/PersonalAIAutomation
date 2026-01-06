# Database Patterns

Rules for SQLAlchemy models and database operations.

## File Structure

```
src/database/<domain>/
├── __init__.py
├── models.py       # SQLAlchemy ORM models
└── operations.py   # CRUD functions
```

## SQLAlchemy Models

Use SQLAlchemy 2.0 style with `Mapped` type hints:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base


class Item(Base):
    """Represents an item in the database."""

    __tablename__ = "items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()", onupdate="now()")

    # Relationships
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("parents.id"), nullable=True)
    parent: Mapped["Parent"] = relationship(back_populates="items")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_items_status", "status"),
        Index("ix_items_created_at", "created_at"),
    )
```

## Operations Pattern

Database operations are pure functions that take a Session:

```python
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from src.database.domain.models import Item

logger = logging.getLogger(__name__)


def get_item_by_id(session: Session, item_id: UUID) -> Item:
    """Get an item by ID.

    :param session: Database session.
    :param item_id: Item ID to find.
    :returns: The item.
    :raises NoResultFound: If item doesn't exist.
    """
    return session.query(Item).filter(Item.id == item_id).one()


def create_item(session: Session, name: str, status: str) -> Item:
    """Create a new item.

    :param session: Database session.
    :param name: Item name.
    :param status: Initial status.
    :returns: The created item.
    """
    item = Item(name=name, status=status)
    session.add(item)
    session.flush()  # Get auto-generated ID
    logger.info(f"Created item: id={item.id}, name={name}")
    return item


def update_item_status(session: Session, item_id: UUID, status: str) -> Item:
    """Update an item's status.

    :param session: Database session.
    :param item_id: Item ID to update.
    :param status: New status.
    :returns: The updated item.
    """
    item = get_item_by_id(session, item_id)
    item.status = status
    session.flush()
    logger.info(f"Updated item status: id={item_id}, status={status}")
    return item


def list_items_by_status(session: Session, status: str) -> list[Item]:
    """List all items with a given status.

    :param session: Database session.
    :param status: Status to filter by.
    :returns: List of matching items.
    """
    return session.query(Item).filter(Item.status == status).all()
```

## Key Principles

1. **Session from caller**: Operations receive Session as first parameter.
2. **No commits in operations**: Caller manages transactions.
3. **Use `.flush()` for IDs**: Get auto-generated IDs without committing.
4. **Log with context**: Include relevant IDs in log messages.

## Session Management

Use a context manager for session handling:

```python
from contextlib import contextmanager
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

engine = create_engine(os.environ["DATABASE_URL"])
SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Usage:

```python
from src.database.connection import get_session
from src.database.items.operations import create_item, get_item_by_id

with get_session() as session:
    item = create_item(session, name="Test", status="pending")
    # Commit happens automatically at end of context
```

## JSONB for Flexible Data

Use JSONB for semi-structured data that doesn't need relational queries:

```python
from sqlalchemy.dialects.postgresql import JSONB

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    # Store conversation messages as JSON array
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Store arbitrary metadata
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

## Indexes

Add indexes on columns used in queries:

```python
__table_args__ = (
    # Single column indexes
    Index("ix_items_status", "status"),
    Index("ix_items_created_at", "created_at"),
    # Composite index for common query patterns
    Index("ix_items_status_created", "status", "created_at"),
    # Foreign key indexes (important for JOIN performance)
    Index("ix_items_parent_id", "parent_id"),
)
```

## Migrations

Use Alembic for schema changes:

```bash
# Create new migration
poetry run alembic revision --autogenerate -m "add items table"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1
```
