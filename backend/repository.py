"""
Repository layer.

All SQL lives here. main.py never touches raw SQL.

Money is stored as INTEGER paise (1 INR = 100 paise) to avoid
floating-point rounding bugs.  We convert at the boundary:
  - On write : Decimal rupees  → int paise
  - On read  : int paise       → Decimal rupees
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Optional

from schemas import ExpenseCreate, ExpenseResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAISE_PER_RUPEE = 100


def _rupees_to_paise(amount: Decimal) -> int:
    return int((amount * _PAISE_PER_RUPEE).to_integral_value())


def _row_to_response(row: sqlite3.Row) -> ExpenseResponse:
    return ExpenseResponse(
        id=row["id"],
        idempotency_key=row["idempotency_key"],
        amount=Decimal(row["amount_paise"]) / _PAISE_PER_RUPEE,
        category=row["category"],
        description=row["description"] or "",
        date=row["date"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

class DuplicateIdempotencyKey(Exception):
    """Raised when the idempotency_key already exists — return existing record."""

    def __init__(self, existing: ExpenseResponse):
        self.existing = existing


def create_expense(conn: sqlite3.Connection, payload: ExpenseCreate) -> ExpenseResponse:
    """
    Insert a new expense.

    If the idempotency_key already exists we return the stored record
    without modifying it (safe retry / exactly-once semantics).
    """
    # Check for existing key first (cheap SELECT before INSERT)
    existing = _fetch_by_idempotency_key(conn,payload.user_id,payload.idempotency_key)
    if existing:
        raise DuplicateIdempotencyKey(existing)

    cursor = conn.execute(
        """
        INSERT INTO expenses (user_id,idempotency_key, amount_paise, category, description, date)
        VALUES (:user_id,:key, :amount_paise, :category, :description, :date)
        """,
        {
            "user_id": payload.user_id,
            "key": payload.idempotency_key,
            "amount_paise": _rupees_to_paise(payload.amount),
            "category": payload.category,
            "description": payload.description,
            "date": payload.date.isoformat(),
        },
    )
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _row_to_response(row)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _fetch_by_idempotency_key(
    conn: sqlite3.Connection,user_id: str,key: str
) -> Optional[ExpenseResponse]:
    row = conn.execute(
        "SELECT * FROM expenses WHERE  user_id = ? AND  idempotency_key = ?", (user_id,key)
    ).fetchone()
    return _row_to_response(row) if row else None


def list_expenses(
        
    conn: sqlite3.Connection,
    *,
        user_id: str,
    category: Optional[str] = None,
    sort: Optional[str] = None,
) -> list[ExpenseResponse]:
    """
    Fetch expenses with optional filtering and sorting.

    Supported sort values:
      - "date_desc"  → newest expense date first (default)
      - "date_asc"   → oldest expense date first
      - "amount_desc"→ highest amount first
      - "amount_asc" → lowest amount first
    """
    query = "SELECT * FROM expenses WHERE user_id = ?"
    params: list = [user_id]


    if category:
        query += " AND category = ?"
        params.append(category)

    # Map sort param → safe ORDER BY clause (never interpolate raw user input)
    order_map = {
        "date_desc": "date DESC, created_at DESC",
        "date_asc": "date ASC, created_at ASC",
        "amount_desc": "amount_paise DESC",
        "amount_asc": "amount_paise ASC",
    }
    order_clause = order_map.get(sort or "date_desc", "date DESC, created_at DESC")
    query += f" ORDER BY {order_clause}"

    rows = conn.execute(query, params).fetchall()
    return [_row_to_response(r) for r in rows]


def get_categories(conn: sqlite3.Connection) -> list[str]:
    """Return distinct categories that have at least one expense."""
    rows = conn.execute(
        "SELECT DISTINCT category FROM expenses ORDER BY category"
    ).fetchall()
    return [r["category"] for r in rows]
