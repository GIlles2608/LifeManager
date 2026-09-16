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

Migrating from the former 5-layer MVC to a Port-Adapter (Hexagonal)
architecture, module by module, starting with `finance/` (see ADR-0001).
Target shape per module:

```
Presentation (PyQt6 Views — primary adapters)
        ↕
Controllers  (signal/slot bindings)
        ↕
Domain       (services + ports — pure Python, no Qt, no SQLAlchemy, no requests)
        ↕  (ports, implemented by …)
Adapters     (SQLAlchemy repositories, HTTP clients — secondary adapters)
        ↕
PostgreSQL / external APIs
```

**Rules:**
- The domain (services + ports) imports no `sqlalchemy`, `PyQt6`, or `requests` —
  only ports it defines itself. Views never import repositories directly.
- A **port** is an interface defined on the domain side (a `Protocol`, see
  `finance/domain/ports/`) describing a need without saying how it's met.
  An **adapter** is a concrete implementation of a port on the infrastructure
  side — SQLAlchemy repositories, HTTP clients, PyQt6 views.
- Services depend only on ports, injected via their constructor — never on
  `Session` or concrete repository classes directly. A manual factory
  (e.g. `finance/bootstrap.py`) is the single place that knows both `Session`
  and the concrete repository classes, and wires them into the service.
- **Services never call `self._session.query/get/scalars` directly** — every DB
  access goes through a repository (adapter) method satisfying the relevant port.
  If a query is missing, add it to the repo, do not bypass it.
- Repositories inherit from `BaseRepository[T]` (`core/repositories/base.py`),
  which provides `add`, `delete`, `get_by_id`, `find_by_id`, `list_all`, and
  satisfy the mirrored `BaseRepositoryPort[T]` structurally (duck typing via
  `Protocol` — no inheritance link required). Subclasses set the `model` class
  attribute and add domain-specific queries.
- No module depends directly on another module's adapters — each module
  (`finance/`, `grocery/`, `nutrition/`) exposes and consumes its own ports.

This migration is formative, not corrective — see ADR-0001 for full context
and success criteria. `FinanceService` is the first service migrated to this
pattern (ADR-0003); other services/modules follow once the approach is
validated there.

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
│   ├── domain/
│   │   └── ports/           # Protocol ports mirroring each repository
│   │                        #   (BaseRepositoryPort[T] + one port per repo)
│   ├── repositories/       # one repo per aggregate, all inherit BaseRepository;
│   │                       # satisfy the matching port structurally (adapters)
│   ├── services/           # FinanceService — constructed via ports, no Session
│   │                       #   (BudgetService planned)
│   ├── bootstrap.py        # build_finance_service(session) factory — the only
│   │                       #   place that knows both Session and concrete repos
│   ├── controllers/        # FinanceController
│   └── views/              # TransactionsView, AddTransactionDialog, etc.
├── grocery/                # Grocery module (planned)
├── nutrition/              # Nutrition module (planned)
├── dashboard/              # Aggregated KPI view (planned)
├── settings/               # User preferences (planned)
└── shared/widgets/         # Reusable PyQt6 widgets (planned)
migrations/                 # Alembic migration files
tests/
├── unit/                   # No DB — session/ports are mocked
└── integration/            # Ephemeral PostgreSQL via testcontainers (ADR-0002)
```

**Import rule for models and repos**: always import from the package, not the
submodule. `from lifemanager.finance.models import Transaction, FlowType` —
not `from lifemanager.finance.models.transaction import …`. The `__init__.py`
re-exports keep the surface stable when files move. Same rule for ports:
import from `lifemanager.finance.domain.ports`, not the submodule.

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

- Unit tests: mock ports/session with `unittest.mock.MagicMock()` — no DB
  required. Services are built by constructing them directly with mocked
  ports (via their constructor), never by monkeypatching private attributes
  after construction (e.g. `svc._tx_repo = MagicMock()` — see ADR-0003).
- Integration tests: run against an ephemeral PostgreSQL container spun up by
  `testcontainers-python` (session-scoped fixture, Alembic migrations applied
  automatically) — no manually-provisioned database required (see ADR-0002).
  Default isolation is per-test rollback (`db_session` fixture); use the
  `truncate_tables` fallback only when the code under test commits explicitly.
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
- Docker is a required environment dependency for integration tests (used by
  `testcontainers-python`, ADR-0002) — dev machines and CI agents must have it
  available. The manually-managed `lifemanager_test` database is retired.

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

## Current state (as of 2026-09-15)

**Architecture migration to Port-Adapter (Hexagonal) underway** — see
ADR-0001, ADR-0002, ADR-0003. `finance/` is the first module migrated;
`grocery/`, `nutrition/` follow once the pattern is validated.

**Finance module:**
- Models: split into one file per aggregate + `enums.py`, all re-exported via
  `lifemanager.finance.models`.
- Repositories: 6 repos (`Account`, `Category`, `Transaction`, `Budget`, `Debt`,
  `SavingsGoal`), all inheriting `BaseRepository[T]` and structurally
  satisfying the matching `Protocol` port in `finance/domain/ports/` — they
  now double as secondary adapters, unchanged in their own code.
- `AccountRepository.get_balance(account_id)` computes balance via SQL
  aggregation (`CASE WHEN sense = 'entree' …`) — never loads transactions in RAM.
  The old `Account.current_balance` property has been removed.
- `FinanceService`: depends only on ports injected via its constructor (no
  `Session`, no concrete repository classes — ADR-0003 complete). Built via
  `finance/bootstrap.py::build_finance_service(session)`, the sole place that
  wires `Session` + concrete repositories together. Exposes
  `create_transaction`, `delete_transaction`, `check_budget`,
  `get_monthly_kpis`, `update_debt_balance`. Returns typed dataclasses
  (`MonthlyKPIs`, `BudgetCheckResult`) instead of dicts.
- KPIs: 5 headline values (Revenus, Dépenses, Épargne, Remb. dettes, Net).
  Savings-goal tracking is intentionally deferred to a future `SavingsGoalService`.
- Tests: 22 unit tests on `FinanceService`, constructed via the port-mocked
  constructor (no private-attribute monkeypatching). Integration tests now
  exist for all 6 repositories under `tests/integration/finance/`, running
  against an ephemeral PostgreSQL via `testcontainers-python` (ADR-0002).

**Initial Alembic migration applied** — all 7 finance tables exist in DB.

**Next planned steps** (resume here):
1. Confirm `FinanceController` and views (`transactions_view.py`,
   `add_transaction_dialog.py`) call `build_finance_service` rather than
   instantiating `FinanceService` directly.
2. Apply the same port/adapter + factory pattern (ADR-0003) to any future
   Finance service (e.g. `BudgetService`, `SavingsGoalService`).
3. Then start the Grocery module using the hexagonal pattern from the outset.
4. Track ADR-0001's success criteria (no `sqlalchemy`/`PyQt6`/`requests`
   imports in `domain/`, domain tests run without PostgreSQL) as more of
   Finance migrates.