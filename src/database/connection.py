"""Database connection and session management."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str:
    """Build the PostgreSQL database URL from environment variables.

    :returns: The database connection URL.
    :raises KeyError: If required environment variables are not set.
    """
    host = os.environ["DATABASE_HOST"]
    port = os.environ.get("DATABASE_PORT", "5432")
    password = os.environ["APP_DB_PASSWORD"]

    return f"postgresql://app:{password}@{host}:{port}/personal_ai_automation"


def create_db_engine(*, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the database.

    :param echo: If True, log all SQL statements.
    :returns: A configured SQLAlchemy engine.
    """
    return create_engine(get_database_url(), echo=echo, pool_pre_ping=True)


@dataclass
class _DatabaseState:
    """Container for database connection state."""

    engine: Engine | None = field(default=None)
    session_factory: sessionmaker[Session] | None = field(default=None)


_state = _DatabaseState()


def get_engine() -> Engine:
    """Get or create the database engine singleton.

    :returns: The database engine.
    """
    if _state.engine is None:
        _state.engine = create_db_engine()
    return _state.engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory singleton.

    :returns: A sessionmaker bound to the database engine.
    """
    if _state.session_factory is None:
        _state.session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _state.session_factory


@contextmanager
def get_session() -> Iterator[Session]:
    """Create a new database session with automatic cleanup.

    Commits on successful completion, rolls back on exception.

    :yields: A database session.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()
