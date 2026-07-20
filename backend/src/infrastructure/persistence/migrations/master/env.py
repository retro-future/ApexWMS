"""Alembic environment for the MasterDB schema.

Invoked programmatically via ``infrastructure.migrations`` — the
sqlalchemy.url is always set on the Config by the caller, never read
from an ini file.
"""

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from infrastructure.persistence.master.models import MasterBase

config = context.config
target_metadata = MasterBase.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported; use the apexwms CLI")
asyncio.run(run_migrations_online())
