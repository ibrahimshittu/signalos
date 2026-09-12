from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from signalos_backend.brokers import store as broker_models  # noqa: F401
from signalos_backend.db import Base
from signalos_backend.execution import store as execution_models  # noqa: F401
from signalos_backend.market import store as market_models  # noqa: F401
from signalos_backend.notifications import store as notification_models  # noqa: F401
from signalos_backend.proposals import store as proposal_models  # noqa: F401
from signalos_backend.users import memory as memory_models  # noqa: F401
from signalos_backend.users import store as user_models  # noqa: F401

config = context.config
if os.getenv("SIGNALOS_ENVIRONMENT") != "test":
    database_url = os.getenv("SIGNALOS_DATABASE_URL")
    if not database_url:
        raise RuntimeError("SIGNALOS_DATABASE_URL is required for migrations")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
