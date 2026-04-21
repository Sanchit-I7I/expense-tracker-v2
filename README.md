# Expense Tracker

A minimal full-stack personal finance tool — FastAPI backend + single-file HTML/JS frontend.

---

## Quick Start (local, end-to-end)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 2. Frontend

```bash
# Open directly in your browser — no build step needed
open frontend/index.html
# or on Linux:
xdg-open frontend/index.html
```

That's it. The frontend points to `http://localhost:8000` by default.

---

## Run Tests

```bash
cd backend
pip install pytest httpx
pytest tests.py -v
```

---

## Project Structure

```
expense-tracker/
├── backend/
│   ├── main.py          ← FastAPI routes (thin — HTTP concerns only)
│   ├── repository.py    ← All SQL in one place
│   ├── schemas.py       ← Pydantic request/response validation
│   ├── database.py      ← SQLite init + connection context manager
│   ├── tests.py         ← pytest suite (unit + integration)
│   ├── requirements.txt
│   └── render.yaml      ← one-click Render deployment
└── frontend/
    └── index.html       ← Entire UI in one file, zero dependencies
```

---

## Key Design Decisions

### Money: INTEGER paise, not FLOAT rupees
Floats cannot represent decimal money exactly (`0.1 + 0.2 ≠ 0.3`).  
All amounts are stored as `INTEGER paise` (₹99.99 → `9999`).  
Conversion happens only at the API boundary using Python's `Decimal` type.  
The client sends and receives a decimal string (`"99.99"`) — never a raw float.

### Idempotency (the retry problem)
The client generates a UUID (`crypto.randomUUID()`) **once per intended submission** and persists it in `sessionStorage`.  
- If the network fails → the user retries → the server sees the same key and returns the existing record (HTTP 200) instead of inserting a duplicate.  
- If the user refreshes after submitting → the key is still in `sessionStorage` → same safe retry.  
- After a confirmed success → key is rotated → next expense gets a fresh key.

### Persistence: SQLite with WAL mode
- Zero infrastructure — one file, included in Python stdlib.
- WAL (Write-Ahead Logging) allows concurrent reads alongside writes.
- Appropriate for single-user / small-team use. Swap in Postgres for multi-user scale (change `database.py` only — repository layer is DB-agnostic).

### Architecture: 3 layers, no framework magic
`main.py` → HTTP only  
`repository.py` → SQL only  
`schemas.py` → validation only  

Each layer is independently testable. Adding an async ORM or swapping SQLite for Postgres touches `database.py` and `repository.py` only.

### Frontend: zero build step
A single `index.html` with no bundler, no npm, no framework.  
This was a deliberate tradeoff for time and deployability — the file opens directly in a browser.  
In production I'd use React + a proper bundler, but for this scope the complexity isn't justified.

---

## Acceptance Criteria Coverage

| # | Requirement | Implemented |
|---|-------------|-------------|
| 1 | Create expense (amount, category, description, date) | ✅ POST /expenses + form |
| 2 | View list of expenses | ✅ GET /expenses + table |
| 3 | Filter by category | ✅ `?category=` param + dropdown + pills |
| 4 | Sort by date newest first | ✅ `?sort=date_desc` (default) |
| 5 | Total of current list | ✅ Returned by API, shown in summary bar |

**Nice-to-haves completed:**
- ✅ Validation (negative amounts, future dates, required fields — frontend + backend)
- ✅ Category summary (breakdown pills with totals)
- ✅ Automated tests (15 test cases)
- ✅ Loading, error, and empty states in UI

---

## Intentional Omissions (timebox trade-offs)

- **Auth** — not in scope; would add JWT middleware + user_id FK to expenses table
- **Edit / delete** — read the brief as append-only ledger; easy to add as `PATCH /expenses/{id}`
- **Pagination** — not needed at this scale; add `limit`/`offset` query params when dataset grows
- **React frontend** — single HTML file is simpler to deploy and meets the spec; refactor when the UI grows
- **Postgres** — SQLite is sufficient; the repository layer makes swapping trivial

---

## Deploy to Render (free tier)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → New → Web Service.
3. Connect the repo, set **Root Directory** to `backend/`.
4. Render auto-detects the `render.yaml` and deploys.
5. Update `API_BASE` in `frontend/index.html` to your Render URL.
6. Host `frontend/index.html` on Render Static Site or any CDN.
