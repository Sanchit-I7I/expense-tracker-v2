from __future__ import annotations

import re
from datetime import date as DateType, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, Field, validator


# ---------------------------------------------------------------------------
# Allowed categories — extend freely
# ---------------------------------------------------------------------------
VALID_CATEGORIES = {
    "Food",
    "Transport",
    "Shopping",
    "Entertainment",
    "Health",
    "Utilities",
    "Education",
    "Travel",
    "Other",
}


class ExpenseCreate(BaseModel):
    """Payload the client sends when creating an expense."""

    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Client-generated unique key (UUID v4 recommended) to allow safe retries.",
    )
    user_id: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., description="Expense amount in INR (e.g. 199.99).")
    category: str = Field(..., description=f"One of: {sorted(VALID_CATEGORIES)}")
    description: str = Field(default="", max_length=500)
    date: DateType = Field(..., description="Date of the expense (YYYY-MM-DD).")

    @validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        # Allow up to 2 decimal places
        quantized = v.quantize(Decimal("0.01"))
        if quantized <= 0:
            raise ValueError("amount must be greater than zero")
        # Guard against absurdly large values (optional: adjust ceiling as needed)
        if quantized > Decimal("10_000_000"):
            raise ValueError("amount exceeds maximum allowed value")
        return quantized

    @validator("category")
    @classmethod
    def category_must_be_valid(cls, v: str) -> str:
        normalised = v.strip().title()
        if normalised not in VALID_CATEGORIES:
            raise ValueError(
                f"'{v}' is not a valid category. Choose from: {sorted(VALID_CATEGORIES)}"
            )
        return normalised

    @validator("idempotency_key")
    @classmethod
    def key_must_be_safe(cls, v: str) -> str:
        # Reject keys with characters that could cause issues
        if not re.match(r"^[A-Za-z0-9_\-]+$", v):
            raise ValueError(
                "idempotency_key may only contain alphanumeric characters, hyphens, and underscores"
            )
        return v

    @validator("date")
    @classmethod
    def date_not_in_future(cls, v: DateType) -> DateType:
        if v > DateType.today():
            raise ValueError("date cannot be in the future")
        return v


class ExpenseResponse(BaseModel):
    """Shape of an expense returned by the API."""

    id: int
    idempotency_key: str
    amount: Decimal          # Returned as decimal rupees, not raw paise
    category: str
    description: str
    date: DateType
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpenseListResponse(BaseModel):
    data: list[ExpenseResponse]
    total: Decimal           # Sum of amount for the current filtered list
    count: int
