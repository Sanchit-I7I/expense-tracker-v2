import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "expenses.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          TEXT    NOT NULL,
                idempotency_key  TEXT    UNIQUE NOT NULL,
                amount_paise     INTEGER NOT NULL CHECK(amount_paise > 0),
                category         TEXT    NOT NULL,
                description      TEXT    NOT NULL DEFAULT '',
                date             TEXT    NOT NULL,
                created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)"
        )
