from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from config import DB_PATH


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Ensure the database schema exists and run lightweight migrations.

    This is safe to call multiple times:
    - CREATE TABLE IF NOT EXISTS is idempotent
    - PRAGMA table_info + ALTER TABLE only runs when columns are missing
    - CREATE INDEX IF NOT EXISTS is idempotent

    If conn is None, this function opens its own connection.
    """
    owns_conn = conn is None

    # Ensure parent directory exists (data/)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)

    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT '',
                tax_deductible INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'EUR',
                payment_method TEXT DEFAULT ''
            )
            """
        )

        # Migration: add columns if DB was created from older schema
        cursor = conn.execute("PRAGMA table_info(expenses)")
        columns = [col[1] for col in cursor.fetchall()]

        if "tax_deductible" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN tax_deductible INTEGER DEFAULT 0")
        if "currency" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN currency TEXT DEFAULT 'EUR'")
        if "payment_method" not in columns:
            conn.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT DEFAULT ''")

        # Indices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_tax ON expenses(tax_deductible)")

        if owns_conn:
            conn.commit()

    finally:
        if owns_conn:
            conn.close()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """
    Open a SQLite connection that is guaranteed to have the schema available.

    Key robustness feature:
    - We call init_db(conn) on every connection, so tools will never fail due to
      missing DB file / missing table when running under `fastmcp dev server.py`.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # Ensure schema exists even if server startup path didn't call init_db()
        init_db(conn)

        yield conn
        conn.commit()
    finally:
        conn.close()
