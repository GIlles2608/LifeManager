"""In-memory fakes standing in for the Finance persistence adapters.

ADR-0006 asks the FinanceService unit tests to run against a `FakeUnitOfWork`
rather than mocks of individual repositories: the fake records commits and
rollbacks, so tests can assert on the transaction boundary itself — something
a MagicMock cannot express.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Self

from lifemanager.finance.application.dto import (
    AccountReadDTO,
    CategoryReadDTO,
    DebtReadDTO,
    SavingsGoalReadDTO,
    TransactionReadDTO,
)
from lifemanager.finance.application.ports import AbstractUnitOfWork
from lifemanager.finance.domain.entities import Budget, Debt
from lifemanager.finance.domain.entities import Transaction as TransactionEntity
from lifemanager.finance.domain.enums import FlowType


class FakeTransactionRepository:
    """Transactions held in a dict, keyed by id."""

    def __init__(self) -> None:
        self.transactions: dict[uuid.UUID, TransactionEntity] = {}
        self.read_rows: dict[uuid.UUID, TransactionReadDTO] = {}
        self.rows_by_month: dict[str, list[TransactionReadDTO]] = {}
        self.spent_by_category: dict[tuple[uuid.UUID, str], Decimal] = {}
        self.totals_by_flow: dict[tuple[FlowType, str], Decimal] = {}
        self.deleted: list[uuid.UUID] = []

    def add(self, entity: TransactionEntity) -> TransactionEntity:
        self.transactions[entity.id] = entity
        return entity

    def delete(self, entity_id: uuid.UUID) -> None:
        self.deleted.append(entity_id)
        self.transactions.pop(entity_id, None)

    def list_by_month_with_relations(self, month: str) -> list[TransactionReadDTO]:
        return self.rows_by_month.get(month, [])

    def read_by_id(self, transaction_id: uuid.UUID) -> TransactionReadDTO | None:
        return self.read_rows.get(transaction_id)

    def total_spent_by_category(self, category_id: uuid.UUID, month: str) -> Decimal:
        return self.spent_by_category.get((category_id, month), Decimal(0))

    def total_by_flow(self, flow_type: FlowType, month: str) -> Decimal:
        return self.totals_by_flow.get((flow_type, month), Decimal(0))


class FakeBudgetRepository:
    def __init__(self) -> None:
        self.budgets: dict[tuple[uuid.UUID, str], Budget] = {}
        self.lookups: list[tuple[uuid.UUID, str]] = []

    def get_by_category_and_month(self, category_id: uuid.UUID, month: str) -> Budget | None:
        self.lookups.append((category_id, month))
        return self.budgets.get((category_id, month))


class FakeCategoryRepository:
    def __init__(self) -> None:
        self.active: list[CategoryReadDTO] = []
        self.by_id: dict[uuid.UUID, CategoryReadDTO] = {}

    def list_active_read(self) -> list[CategoryReadDTO]:
        return self.active

    def find_read_by_id(self, entity_id: uuid.UUID) -> CategoryReadDTO | None:
        return self.by_id.get(entity_id)


class FakeDebtRepository:
    def __init__(self) -> None:
        self.debts: dict[uuid.UUID, Debt] = {}
        self.active: list[DebtReadDTO] = []
        self.saved: list[Debt] = []

    def find_domain_by_id(self, entity_id: uuid.UUID) -> Debt | None:
        return self.debts.get(entity_id)

    def save_domain(self, entity: Debt) -> Debt:
        self.debts[entity.id] = entity
        self.saved.append(entity)
        return entity

    def list_active_read(self) -> list[DebtReadDTO]:
        return self.active


class FakeAccountRepository:
    def __init__(self) -> None:
        self.active: list[AccountReadDTO] = []

    def list_active_read(self) -> list[AccountReadDTO]:
        return self.active


class FakeSavingsGoalRepository:
    def __init__(self) -> None:
        self.active: list[SavingsGoalReadDTO] = []

    def list_active_read(self) -> list[SavingsGoalReadDTO]:
        return self.active


class FakeUnitOfWork(AbstractUnitOfWork):
    """In-memory unit of work recording its transaction boundary."""

    def __init__(self) -> None:
        self.tx_repo = FakeTransactionRepository()
        self.budget_repo = FakeBudgetRepository()
        self.category_repo = FakeCategoryRepository()
        self.debt_repo = FakeDebtRepository()
        self.account_repo = FakeAccountRepository()
        self.goal_repo = FakeSavingsGoalRepository()
        self.commits = 0
        self.rollbacks = 0
        self.entered = 0

    def __enter__(self) -> Self:
        self.entered += 1
        return self

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    # ── Test helpers ──────────────────────────────────────────────────────────

    def given_transaction_read_row(self, row: TransactionReadDTO) -> None:
        """Make `read_by_id` return `row` for whichever transaction is added."""
        self.tx_repo.read_rows[row.id] = row

    def given_budget(self, budget: Budget, month: str) -> None:
        self.budget_repo.budgets[(budget.category_id, month)] = budget

    def given_category(self, category: CategoryReadDTO) -> None:
        self.category_repo.by_id[category.id] = category

    def given_debt(self, debt: Debt) -> None:
        self.debt_repo.debts[debt.id] = debt

    def with_balance(self, debt: Debt, balance: Decimal) -> Debt:
        return replace(debt, current_balance=balance)
