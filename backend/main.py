"""
Expense Tracker API
===================
Entry point.  Keep this thin — routing + HTTP concerns only.
Business logic lives in repository.py, schema validation in schemas.py.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from database import get_db, init_db
from repository import (
    DuplicateIdempotencyKey,
    create_expense,
    get_categories,
    list_expenses,
)
from schemas import ExpenseCreate, ExpenseListResponse, ExpenseResponse, VALID_CATEGORIES

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("expense_tracker")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Expense Tracker API",
    description="A minimal personal finance API with idempotent expense creation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production (list your front-end origin)
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialised")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post(
    "/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new expense",
    responses={
        200: {"description": "Duplicate idempotency_key — returning existing record"},
        201: {"description": "Expense created successfully"},
        422: {"description": "Validation error"},
    },
)
def post_expense(payload: ExpenseCreate):
    """
    Create a new expense.

    **Idempotency**: include a unique `idempotency_key` (UUID v4 recommended)
    in every request.  If the network times out and you retry, the server will
    detect the duplicate key and return the already-stored record with HTTP 200
    instead of creating a second entry.
    """
    with get_db() as conn:
        try:
            expense = create_expense(conn, payload)
            logger.info("Created expense id=%s key=%s", expense.id, payload.idempotency_key)
            return expense
        except DuplicateIdempotencyKey as dup:
            # Safe retry — tell the client we already have this one
            logger.info(
                "Duplicate idempotency_key=%s → returning existing id=%s",
                payload.idempotency_key,
                dup.existing.id,
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=dup.existing.model_dump(mode="json"),
            )


@app.get(
    "/expenses",
    response_model=ExpenseListResponse,
    summary="List expenses",
)
def get_expenses(
    user_id: str,
    category: Optional[str] = Query(
        default=None,
        description="Filter by category name (case-sensitive).",
    ),
    sort: Optional[str] = Query(
        default="date_desc",
        description="Sort order: date_desc | date_asc | amount_desc | amount_asc",
    ),
):
    """
    Return a list of expenses with optional **category filter** and **sort**.

    Also returns a `total` field — the sum of all *currently visible* expenses.
    """
    valid_sorts = {"date_desc", "date_asc", "amount_desc", "amount_asc"}
    if sort and sort not in valid_sorts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort value '{sort}'. Choose from: {sorted(valid_sorts)}",
        )

    if category and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown category '{category}'. Choose from: {sorted(VALID_CATEGORIES)}",
        )

    with get_db() as conn:
        expenses = list_expenses(conn,user_id=user_id, category=category, sort=sort)

    total = sum((e.amount for e in expenses), Decimal("0.00"))

    return ExpenseListResponse(
        data=expenses,
        total=total,
        count=len(expenses),
    )


@app.get(
    "/categories",
    response_model=list[str],
    summary="List categories that have at least one expense",
)
def get_used_categories():
    """Convenience endpoint — returns only categories that actually have data."""
    with get_db() as conn:
        return get_categories(conn)


@app.get("/health", include_in_schema=False)
def health():
    """Simple liveness check for load balancers / uptime monitors."""
    return {"status": "ok"}
