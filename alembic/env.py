"""Alembic environment configuration."""

from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy.engine import Engine

from alembic import context
from src.database.connection import create_db_engine, get_database_url
from src.database.core import Base
from src.database.agent_tracking.models import *  # noqa: F403
from src.database.alerts.models import *  # noqa: F403
from src.database.extraction_state.models import *  # noqa: F403
from src.database.medium.models import *  # noqa: F403
from src.database.newsletters.models import *  # noqa: F403
from src.database.reminders.models import *  # noqa: F403
from src.database.substack.models import *  # noqa: F403
from src.database.telegram.models import *  # noqa: F403

# Load environment variables
load_dotenv()

# This is the Alembic Config object
config = context.config

# Set up Python logging from config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() emit SQL to the script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable: Engine = create_db_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
