"""Database configuration and session management."""

import contextlib
import os
import sqlite3
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .utils import parse_size

DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR}/sessions.db")

# Retention defaults (read at call time so tests/env changes take effect).
DEFAULT_KEEP_RECENT = 10

engine = create_engine(DATABASE_URL, echo=False)


def get_configured_max_bytes() -> int | None:
    """Size cap from WEBREPORTLOG_MAX_DB_SIZE, or None if unset. Raises ValueError if bad."""
    raw = os.getenv("WEBREPORTLOG_MAX_DB_SIZE")
    return parse_size(raw) if raw else None


def get_configured_keep_recent() -> int:
    """Number of newest sessions to protect from pruning (WEBREPORTLOG_KEEP_RECENT)."""
    raw = os.getenv("WEBREPORTLOG_KEEP_RECENT")
    return int(raw) if raw else DEFAULT_KEEP_RECENT


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraint enforcement for SQLite connections."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_database_path() -> str | None:
    """Return the on-disk path of the SQLite database, or None if not file-backed."""
    db_path = engine.url.database
    if not db_path or db_path == ":memory:":
        return None
    return db_path


def get_database_size_bytes() -> int | None:
    """Return the database size on disk in bytes (including -wal/-shm sidecars).

    Returns None for non-file databases or if the file cannot be read yet.
    """
    path = get_database_path()
    if path is None:
        return None
    try:
        total = os.path.getsize(path)
    except OSError:
        return None
    for suffix in ("-wal", "-shm"):
        with contextlib.suppress(OSError):  # sidecar absent — fine
            total += os.path.getsize(path + suffix)
    return total


def create_db_and_tables():
    """Create database tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def ensure_columns() -> None:
    """Add columns introduced after a database was first created.

    SQLModel.create_all() only creates missing tables, never alters existing ones,
    so additive schema changes need an explicit (idempotent) ALTER for older DBs.
    """
    # column name -> SQL definition for ALTER TABLE ... ADD COLUMN
    expected = {
        "logs_pruned": "BOOLEAN NOT NULL DEFAULT 0",
        "env_metadata": "TEXT DEFAULT NULL",
    }
    with engine.begin() as conn:
        existing = {
            row[1]  # (cid, name, type, notnull, dflt_value, pk)
            for row in conn.exec_driver_sql("PRAGMA table_info(session)").fetchall()
        }
        for name, ddl in expected.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE session ADD COLUMN {name} {ddl}")


def vacuum() -> None:
    """Reclaim free pages to the OS (shrinks the file on disk)."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql("VACUUM")


def get_session():
    """Get database session for dependency injection."""
    with Session(engine) as session:
        yield session
