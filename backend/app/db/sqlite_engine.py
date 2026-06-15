"""SQLite engine helpers (sync + async).

We expose:
  - get_sync_conn()   — for seeders and one-off scripts
  - get_async_conn()  — for the FastAPI request lifecycle (aiosqlite)
  - bootstrap()       — applies schema.sql and seeds on first boot
"""
from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import aiosqlite

from app.observability import get_logger
from app.settings import get_settings

logger = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _apply_schema_sync(db_path: Path) -> None:
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


@contextmanager
def get_sync_conn():
    settings = get_settings()
    db_path = settings.sqlite_abs_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def get_async_conn():
    settings = get_settings()
    db_path = settings.sqlite_abs_path
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
    finally:
        await conn.close()


def bootstrap() -> None:
    """Idempotent: ensures DB exists, schema applied, seed loaded if empty."""
    settings = get_settings()
    db_path = settings.sqlite_abs_path
    is_new = not db_path.exists()
    _apply_schema_sync(db_path)
    if is_new:
        logger.info("Fresh SQLite at %s — running seeder.", db_path)
    # Even on existing DB, check if customers is empty.
    with get_sync_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()
        if row["c"] == 0:
            logger.info("customers table is empty — seeding.")
            from app.db.seeders.faker_seed import run_seed

            run_seed(conn)
            conn.commit()
            logger.info("Seed complete.")
        else:
            logger.info("DB already populated (%d customers).", row["c"])
