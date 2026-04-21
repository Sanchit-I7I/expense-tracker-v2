"""
Automated tests for the Expense Tracker API.

Run with:
    pip install pytest httpx
    pytest tests.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

# Use an in-memory / temp DB for tests — never touch the real one
os.environ["DB_PATH"] = ":memory:"

from main import app  # noqa: E402  (import after env var is set)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_expense(**overrides):
    defaults = {
        "idempotency_key": str(uuid.uuid4()),
        "amount": "250.00",
        "category": "Food",
        "description": "Lunch at canteen",
        "date": "2024-06-15",
    }
    return {**defaults, **overrides}


# ---------------------------------------------------------------------------
# POST /expenses
# ---------------------------------------------------------------------------

class TestCreateExpense:
    def test_creates_successfully(self):
        payload = _make_expense()
        r = client.post("/expenses", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["amount"] == "250.00"
        assert body["category"] == "Food"
        assert "id" in body

    def test_idempotency_returns_200_on_retry(self):
        payload = _make_expense()
        r1 = client.post("/expenses", json=payload)
        assert r1.status_code == 201

        # Retry with same key — must NOT create a duplicate
        r2 = client.post("/expenses", json=payload)
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_idempotency_different_keys_create_two_records(self):
        base = _make_expense(description="Same content")
        r1 = client.post("/expenses", json={**base, "idempotency_key": str(uuid.uuid4())})
        r2 = client.post("/expenses", json={**base, "idempotency_key": str(uuid.uuid4())})
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    def test_rejects_negative_amount(self):
        r = client.post("/expenses", json=_make_expense(amount="-10"))
        assert r.status_code == 422

    def test_rejects_zero_amount(self):
        r = client.post("/expenses", json=_make_expense(amount="0"))
        assert r.status_code == 422

    def test_rejects_invalid_category(self):
        r = client.post("/expenses", json=_make_expense(category="Gambling"))
        assert r.status_code == 422

    def test_rejects_future_date(self):
        r = client.post("/expenses", json=_make_expense(date="2099-01-01"))
        assert r.status_code == 422

    def test_amount_stored_as_decimal(self):
        r = client.post("/expenses", json=_make_expense(amount="99.99"))
        assert r.status_code == 201
        # Must come back as exact decimal, not floating-point garbage
        assert r.json()["amount"] == "99.99"


# ---------------------------------------------------------------------------
# GET /expenses
# ---------------------------------------------------------------------------

class TestListExpenses:
    def setup_method(self):
        """Seed a few expenses before each test in this class."""
        self.key_food_1 = str(uuid.uuid4())
        self.key_food_2 = str(uuid.uuid4())
        self.key_transport = str(uuid.uuid4())

        client.post("/expenses", json=_make_expense(
            idempotency_key=self.key_food_1,
            category="Food", amount="100.00", date="2024-06-10"
        ))
        client.post("/expenses", json=_make_expense(
            idempotency_key=self.key_food_2,
            category="Food", amount="200.00", date="2024-06-20"
        ))
        client.post("/expenses", json=_make_expense(
            idempotency_key=self.key_transport,
            category="Transport", amount="50.00", date="2024-06-15"
        ))

    def test_returns_all_expenses(self):
        r = client.get("/expenses")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 3

    def test_filter_by_category(self):
        r = client.get("/expenses", params={"category": "Food"})
        body = r.json()
        assert all(e["category"] == "Food" for e in body["data"])

    def test_total_reflects_filter(self):
        r = client.get("/expenses", params={"category": "Food"})
        body = r.json()
        computed = sum(float(e["amount"]) for e in body["data"])
        assert abs(float(body["total"]) - computed) < 0.01

    def test_sort_date_desc(self):
        r = client.get("/expenses", params={"sort": "date_desc"})
        dates = [e["date"] for e in r.json()["data"]]
        assert dates == sorted(dates, reverse=True)

    def test_sort_date_asc(self):
        r = client.get("/expenses", params={"sort": "date_asc"})
        dates = [e["date"] for e in r.json()["data"]]
        assert dates == sorted(dates)

    def test_invalid_sort_returns_400(self):
        r = client.get("/expenses", params={"sort": "random_field"})
        assert r.status_code == 400

    def test_invalid_category_returns_400(self):
        r = client.get("/expenses", params={"category": "Crypto"})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
