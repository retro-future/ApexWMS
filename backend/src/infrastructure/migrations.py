"""Programmatic Alembic runner for both schema kinds.

No alembic.ini: the script location is derived from this package and the
database URL is injected per run — required because tenant migrations
run against N databases (PRD §3.2), not one configured URL.

``upgrade()`` is safe to call from async code: Alembic's env.py drives
its own event loop, so it runs in a worker thread.
"""

import asyncio
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

SchemaKind = Literal["master", "tenant"]

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "persistence" / "migrations"


def _config(kind: SchemaKind, db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR / kind))
    # Config values are ini-interpolated; escape literal % (e.g. in passwords).
    cfg.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return cfg


def head_revision(kind: SchemaKind) -> str:
    """The revision ``upgrade(kind, ...)`` brings a database to.

    Read from the migration scripts rather than written down anywhere, so
    "is this database current?" keeps meaning the same thing after the next
    revision lands.
    """
    head = ScriptDirectory.from_config(_config(kind, "")).get_current_head()
    if head is None:
        raise RuntimeError(f"no {kind} migrations found")
    return head


def upgrade_sync(kind: SchemaKind, db_url: str) -> None:
    command.upgrade(_config(kind, db_url), "head")


async def upgrade(kind: SchemaKind, db_url: str) -> None:
    await asyncio.to_thread(upgrade_sync, kind, db_url)


async def current_revision(db_url: str) -> str | None:
    """The alembic_version of a database, or None if never migrated."""
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            exists = await conn.scalar(
                text("SELECT to_regclass('alembic_version') IS NOT NULL")
            )
            if not exists:
                return None
            return await conn.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()
