"""
Alembic env.py — Async SQLAlchemy Migration Runner

Reads DATABASE_URL from environment (same as the app).
Supports both SQLite (dev) and PostgreSQL (production).
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure project root is on sys.path so models can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infrastructure.db.session import Base

# Import ALL models so Base.metadata has all tables
from src.infrastructure.db.models import session_model, task_model, message_model  # noqa
from src.infrastructure.db.models.tenant_model import TenantModel, OrganizationModel, UserModel  # noqa
from src.infrastructure.db.models.folder_model import FolderModel  # noqa
from src.infrastructure.db.models.workspace_model import WorkspaceModel  # noqa

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the app's DATABASE_URL if set, else fall back to alembic.ini
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url", "sqlite+aiosqlite:///./kernel.db"),
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL script."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to DB directly."""
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
