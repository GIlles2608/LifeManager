# CLAUDE.md — LifeManager project context

## Project overview

Desktop application for personal life management — finances, grocery tracking,
and nutrition. Built for solo use on a local machine with a local database.

---

## Language & runtime

- **Python 3.11+** — strictly Python 3, no Python 2 compatibility needed
- Type hints are mandatory on all functions and class attributes (`from __future__ import annotations`)
- Use `|` union syntax over `Optional[X]` (Python 3.10+ style)

---

## Stack

| Layer | Tool | Role |
|---|---|---|
| UI | PyQt6 | Desktop interface — widgets coded in Python, no Qt Designer |
| ORM | SQLAlchemy 2.0 | Maps Python objects ↔ database rows |
| Migrations | Alembic | Tracks and applies schema changes |
| Database | PostgreSQL (local) | Primary datastore |
| Config | python-dotenv | Loads `.env` at startup |
| HTTP | requests | Open Food Facts API calls |
| Testing | pytest + pytest-qt | Unit and integration tests |
| Linting | ruff | Formatting and import sorting |
| Types | mypy (strict) | Static type checking |

---

## Architecture

5-layer MVC with explicit service and repository layers:

```
Presentation (PyQt6 Views)
        ↕
Controllers  (signal/slot bindings)
        ↕
Services     (business logic — pure Python, no Qt, no SQLAlchemy)
        ↕
Repositories (SQLAlchemy queries — only layer that imports ORM)
        ↕
PostgreSQL
```

**Rules:**
- Views never import repositories. Services never import Qt.
- Each layer only talks to the layer directly below it.
- **Services never call `self._session.query/get/scalars` directly** — every DB
  access goes through a repository method. If a query is missing, add it to the
  repo, do not bypass it.
- Repositories inherit from `BaseRepository[T]` (`core/repositories/base.py`),
  which provides `add`, `delete`, `get_by_id`, `find_by_id`, `list_all`.
  Subclasses set the `model` class attribute and add domain-specific queries.

---

## Module structure

```
lifemanager/
├── core/                   # Shared infrastructure
│   ├── config/             # settings.py (singleton), database.py (session factory)
│   ├── models/             # base.py — BaseModel with UUID PK + timestamps
│   ├── repositories/       # base.py — BaseRepository[T] generic CRUD
│   ├── events/             # bus.py — in-process event bus + Events constants
│   └── exceptions/         # exceptions.py — full exception hierarchy
├── finance/                # Finance module
│   ├── models/             # one model per file:
│   │                       #   account.py, category.py, transaction.py,
│   │                       #   budget.py, debt.py, savings_goal.py, alert.py
│   │                       # + enums.py (FlowType, SenseType, AccountType, …)
│   │                       # __init__.py re-exports everything
│   ├── repositories/       # one repo per aggregate, all inherit BaseRepository
│   ├── services/           # FinanceService (BudgetService planned)
│   ├── controllers/        # FinanceController (planned)
│   └── views/              # TransactionView, BudgetView, etc. (planned)
├── grocery/                # Grocery module (planned)
├── nutrition/              # Nutrition module (planned)
├── dashboard/              # Aggregated KPI view (planned)
├── settings/               # User preferences (planned)
└── shared/widgets/         # Reusable PyQt6 widgets (planned)
migrations/                 # Alembic migration files
tests/
├── unit/                   # No DB — session is mocked
└── integration/            # Real test DB required
```

**Import rule for models and repos**: always import from the package, not the
submodule. `from lifemanager.finance.models import Transaction, FlowType` —
not `from lifemanager.finance.models.transaction import …`. The `__init__.py`
re-exports keep the surface stable when files move.

---

## Key domain rules

- Every entity inherits `BaseModel` — gets UUID primary key, `created_at`, `updated_at`
- `Transaction.signed_amount` is positive for entries (`ENTREE`), negative for exits (`SORTIE`)
- `Transaction.month` returns `"YYYY-MM"` string — used for all monthly grouping
- A `DETTE` transaction **must** reference a `Debt`; an `EPARGNE` transaction
  **must** reference a `SavingsGoal`. Conversely, `debt_id`/`goal_id` are only
  allowed on their respective flow types (enforced in `FinanceService._validate_transaction`).
- `Category` is **transverse** to `flow_type` — any transaction (REVENU, DEPENSE,
  DETTE, EPARGNE, TRANSFERT) may carry a category, and the category remains
  optional in every case. Reporting that wants "actual spending only" filters on
  `flow_type=DEPENSE` (e.g. `total_spent_by_category`); reporting that wants
  "everything tagged X" does not filter.
- `Category` is self-referencing — max depth 2 (category → sub-category)
- `GroceryList.to_transaction()` is a domain method, not a service method
- `NutritionService` is non-blocking — missing nutritional data never prevents saving

### Aggregation semantics (TransactionRepository)

`total_*` methods return **unsigned magnitudes** (`Decimal >= 0`); direction is
carried by the `sense` column, never by the sign of the returned value.
`cashflow(month)` is the only signed aggregate, derived from `sense` only
(`total_in - total_out`), independent of `flow_type`.

`MonthlyKPIs.net = revenues - expenses - savings - debt_repayments` —
"disposable cash after committed allocations", **not** raw cashflow.
Use `TransactionRepository.cashflow(month)` for raw cashflow.

---

## Configuration

- Settings loaded from `.env` via `python-dotenv`, accessed as a frozen singleton:
  `from lifemanager.core.config.settings import settings`
- Database session via context manager:
  `from lifemanager.core.config.database import get_session`
- Never instantiate settings or sessions directly — always use these imports

---

## Event bus

Inter-module communication goes through the event bus, not direct imports:

```python
from lifemanager.core.events.bus import bus, Events

# Emit
bus.emit(Events.TRANSACTION_CREATED, transaction)

# Subscribe (at startup)
bus.on(Events.TRANSACTION_CREATED, dashboard_ctrl.refresh)
```

Defined event constants are in `Events` class in `bus.py`. Add new events there.

---

## Coding conventions

- All modules start with `from __future__ import annotations`
- Docstrings on all public classes and methods (one-line for simple, multi-line for complex)
- No raw SQL — all queries go through SQLAlchemy in repository classes
- DTOs (dataclasses) carry data from controller to service — never pass raw dicts
- Enums for all fixed-value fields (`FlowType`, `SenseType`, `AccountType`, etc.)
- `session.flush()` after `add()` in repositories — not `commit()` (commit is the session manager's job)
- Errors raised as domain exceptions from `core/exceptions/exceptions.py`, never generic `Exception`

---

## Testing rules

- Unit tests: mock the session with `unittest.mock.MagicMock()` — no DB required
- Integration tests: use a dedicated test database (`lifemanager_test`)
- Never test PyQt6 widgets in unit tests — use `pytest-qt` fixtures for UI tests
- Test file mirrors source path: `lifemanager/finance/services/finance_service.py`
  → `tests/unit/finance/test_finance_service.py`

---

## Database

- Driver: `psycopg2-binary`
- Migrations managed by Alembic — never modify tables manually in psql
- After modifying a model: `alembic revision --autogenerate -m "description"` then `alembic upgrade head`
- New model **packages** must be imported in `migrations/env.py` (the package
  `__init__.py` re-exports its models, which is enough to register them on
  `Base.metadata`). Pattern: `import lifemanager.<module>.models  # noqa: F401`

---

## Commands reference

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # install project + dev tools in editable mode
cp .env.example .env         # then fill in DB credentials

# Database
psql -U postgres -c "CREATE DATABASE lifemanager;"
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1         # rollback one migration

# Run
python -m lifemanager

# Quality
pytest                       # all tests
pytest tests/unit/ -v        # unit tests only (no DB needed)
ruff check lifemanager/      # linting
mypy lifemanager/            # type checking
```

---

## What is NOT in scope (v1)

- Multi-user support
- Cloud sync or remote database
- Mobile interface
- Bank statement auto-import (planned for v2)
- Web API (planned for v2)

---

## Current state (as of 2026-05-06)

**Finance module — backend layers complete:**
- Models: split into one file per aggregate + `enums.py`, all re-exported via
  `lifemanager.finance.models`.
- Repositories: 6 repos (`Account`, `Category`, `Transaction`, `Budget`, `Debt`,
  `SavingsGoal`), all inheriting `BaseRepository[T]`.
- `AccountRepository.get_balance(account_id)` computes balance via SQL
  aggregation (`CASE WHEN sense = 'entree' …`) — never loads transactions in RAM.
  The old `Account.current_balance` property has been removed.
- `FinanceService`: depends only on repositories. Exposes `create_transaction`,
  `delete_transaction`, `check_budget`, `get_monthly_kpis`, `update_debt_balance`.
  Returns typed dataclasses (`MonthlyKPIs`, `BudgetCheckResult`) instead of dicts.
- KPIs: 5 headline values (Revenus, Dépenses, Épargne, Remb. dettes, Net).
  Savings-goal tracking is intentionally deferred to a future `SavingsGoalService`.
- Tests: 22 unit tests on `FinanceService`, all green. No integration tests yet.

**Initial Alembic migration applied** — all 7 finance tables exist in DB.

**Next planned steps** (resume here):
1. `FinanceController` (opens session via `get_session()`, calls service).
2. First PyQt6 view (transaction list + add).
3. Then start the Grocery module.
4. Optional but valuable: integration tests for repos against a real
   `lifemanager_test` DB to validate Postgres-specific SQL (`to_char`, `CASE WHEN`).