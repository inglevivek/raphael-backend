import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object
config = context.config

# Set up loggers
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Import Base and models for autogenerate support
from app.database import Base
from app.models import User, Course, CourseCheckpoint  # noqa: F401 — force model registration

target_metadata = Base.metadata

# Get DATABASE_URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    config.set_main_option('sqlalchemy.url', DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures context with just a URL, not an Engine.
    Calls to context.execute() emit the string to script output.
    """
    url = config.get_main_option("sqlalchemy.url")
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

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
