"""
Cloud Database Service
======================

All database access in the application goes through this module.
That means migrating from local SQLite to a managed cloud database
(Supabase Postgres, Amazon RDS, Cloud SQL) requires changing ONLY this file.

Every query uses parameter binding (`?`) which is what protects the app
from SQL injection.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

from flask import current_app, g

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "backend" / "db" / "schema.sql"


# ---------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------
def _connect(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")  # enforce FK constraints
    return conn


def get_db() -> sqlite3.Connection:
    """Return the request-scoped connection (created lazily)."""
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exception: Optional[BaseException] = None) -> None:
    """Close the request-scoped connection. Registered as a teardown hook."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app) -> None:
    """Create all tables/indexes. Safe to call on every startup (idempotent)."""
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = _connect(app.config["DATABASE_PATH"])
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Query helpers — the ONLY functions routes should call
# ---------------------------------------------------------------------
def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    """Run a SELECT and return every row as a dict."""
    cursor = get_db().execute(sql, tuple(params))
    try:
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
    """Run a SELECT and return the first row (or None)."""
    cursor = get_db().execute(sql, tuple(params))
    try:
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()


def query_scalar(sql: str, params: Iterable[Any] = (), default: Any = 0) -> Any:
    """Run a SELECT that returns a single value (e.g. COUNT(*))."""
    cursor = get_db().execute(sql, tuple(params))
    try:
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return default
        return row[0]
    finally:
        cursor.close()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Run INSERT/UPDATE/DELETE. Returns the number of affected rows."""
    db = get_db()
    cursor = db.execute(sql, tuple(params))
    db.commit()
    try:
        return cursor.rowcount
    finally:
        cursor.close()


def execute_returning_id(sql: str, params: Iterable[Any] = ()) -> int:
    """Run an INSERT and return lastrowid (used for AUTOINCREMENT tables)."""
    db = get_db()
    cursor = db.execute(sql, tuple(params))
    db.commit()
    try:
        return cursor.lastrowid
    finally:
        cursor.close()


def run_in_transaction(statements: list[tuple[str, Iterable[Any]]]) -> None:
    """
    Execute several statements atomically.

    This is the rollback mechanism: if any statement fails, NOTHING is
    committed — critical for e.g. "create goal + its milestones".
    """
    db = get_db()
    try:
        for sql, params in statements:
            db.execute(sql, tuple(params))
        db.commit()
    except Exception:
        db.rollback()
        raise