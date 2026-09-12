"""
FinanceService — business logic for finance operations.

Orchestrates repositories, enforces domain rules, emits events.
Never touches SQLAlchemy directly: all DB access flows through repositories.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from lifemanager.core.events.bus import Events, bus
from lifemanager.core.exceptions.exceptions import NotFoundError, ValidationError
from lifemanager.finance.models import (
    Account,
    Category,
    Debt,
    FlowType,
    SavingsGoal,
    SenseType,
    Transaction,
)
from lifemanager.finance.repositories import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    DebtRepository,
    SavingsGoalRepository,
    TransactionRepository,
)


# ── DTOs ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TransactionDTO:
    """Validated input from controller to service. Frozen — value object."""
    date: date
    amount: Decimal
    flow_type: FlowType
    sense: SenseType
    label: str
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    debt_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None


@dataclass(frozen=True)
class BudgetCheckResult:
    category_name: str
    ceiling: Decimal
    spent: Decimal
    remaining: Decimal
    is_exceeded: bool


@dataclass(frozen=True)
class MonthlyKPIs:
    """5 headline KPIs for a month. Savings goals are tracked separately."""
    month: str
    revenues: Decimal
    expenses: Decimal
    savings: Decimal
    debt_repayments: Decimal
    net: Decimal


# ── Service ───────────────────────────────────────────────────────────────────

class FinanceService:
    """
    All finance business logic lives here. Instantiated per request with a
    session injected; the service owns its repos but never the session itself
    (commit/rollback is the caller's responsibility, via get_session()).
    """

    def __init__(self, session: Session) -> None:
        self._tx_repo = TransactionRepository(session)
        self._budget_repo = BudgetRepository(session)
        self._category_repo = CategoryRepository(session)
        self._debt_repo = DebtRepository(session)
        self._account_repo = AccountRepository(session)
        self._goal_repo = SavingsGoalRepository(session)

    # ── Transactions ──────────────────────────────────────────────────────────

    def create_transaction(self, dto: TransactionDTO) -> Transaction:
        """Validate, persist, check budget if applicable, emit events."""
        self._validate_transaction(dto)

        tx = Transaction(
            date=dto.date,
            amount=dto.amount,
            flow_type=dto.flow_type.value,
            sense=dto.sense.value,
            label=dto.label,
            account_id=dto.account_id,
            category_id=dto.category_id,
            debt_id=dto.debt_id,
            goal_id=dto.goal_id,
        )
        self._tx_repo.add(tx)

        if dto.flow_type == FlowType.DEPENSE and dto.category_id is not None:
            check = self.check_budget(dto.category_id, tx.month)
            if check.is_exceeded:
                bus.emit(Events.BUDGET_EXCEEDED, check)

        bus.emit(Events.TRANSACTION_CREATED, tx)
        return tx

    def delete_transaction(self, transaction_id: uuid.UUID) -> None:
        self._tx_repo.delete(transaction_id)
        bus.emit(Events.TRANSACTION_DELETED, transaction_id)

    def list_transactions(self, month: str) -> list[Transaction]:
        """Return transactions for the month, with account and category eager-loaded."""
        return self._tx_repo.list_by_month_with_relations(month)

    # ── Lookups (used by UI to populate selectors) ────────────────────────────

    def list_accounts(self) -> list[Account]:
        return self._account_repo.list_active()

    def list_categories(self) -> list[Category]:
        return self._category_repo.list_active()

    def list_active_debts(self) -> list[Debt]:
        return self._debt_repo.list_active()

    def list_active_goals(self) -> list[SavingsGoal]:
        return self._goal_repo.list_active()

    # ── Budget ────────────────────────────────────────────────────────────────

    def check_budget(self, category_id: uuid.UUID, month: str) -> BudgetCheckResult:
        """
        Compare actual spending vs budget ceiling for a (category, month).
        If no budget is defined, ceiling=0 and is_exceeded=False (no rule to break).
        """
        budget = self._budget_repo.get_by_category_and_month(category_id, month)
        category = self._category_repo.find_by_id(category_id)

        ceiling = budget.ceiling if budget is not None else Decimal("0")
        spent = self._tx_repo.total_spent_by_category(category_id, month)
        remaining = ceiling - spent

        return BudgetCheckResult(
            category_name=category.name if category is not None else "Inconnu",
            ceiling=ceiling,
            spent=spent,
            remaining=max(remaining, Decimal("0")),
            is_exceeded=ceiling > 0 and spent > ceiling,
        )

    # ── KPIs ──────────────────────────────────────────────────────────────────

    def get_monthly_kpis(self, month: str) -> MonthlyKPIs:
        """
        5 headline KPIs for a month. Net = Revenues − Expenses − Savings − DebtRepayments.

        Savings and debt repayments are subtracted from Net even though their
        cash already left via SORTIE transactions: Net here represents
        "disposable cash left after committed allocations", not raw cashflow.
        For raw cashflow use TransactionRepository.cashflow(month).
        """
        revenues = self._tx_repo.total_by_flow(FlowType.REVENU, month)
        expenses = self._tx_repo.total_by_flow(FlowType.DEPENSE, month)
        savings = self._tx_repo.total_by_flow(FlowType.EPARGNE, month)
        debts = self._tx_repo.total_by_flow(FlowType.DETTE, month)

        return MonthlyKPIs(
            month=month,
            revenues=revenues,
            expenses=expenses,
            savings=savings,
            debt_repayments=debts,
            net=revenues - expenses - savings - debts,
        )

    # ── Debt ──────────────────────────────────────────────────────────────────

    def update_debt_balance(
        self, debt_id: uuid.UUID, new_balance: Decimal
    ) -> None:
        if new_balance < 0:
            raise ValidationError("Debt balance cannot be negative.")
        debt = self._debt_repo.find_by_id(debt_id)
        if debt is None:
            raise NotFoundError("Debt", debt_id)
        debt.current_balance = new_balance
        bus.emit(Events.DEBT_UPDATED, debt)

    # ── Private ───────────────────────────────────────────────────────────────

    def _validate_transaction(self, dto: TransactionDTO) -> None:
        if dto.amount <= 0:
            raise ValidationError("Transaction amount must be positive.")
        if not dto.label.strip():
            raise ValidationError("Transaction label cannot be empty.")
        if dto.flow_type == FlowType.DETTE and dto.debt_id is None:
            raise ValidationError("A DETTE transaction must reference a Debt.")
        if dto.flow_type == FlowType.EPARGNE and dto.goal_id is None:
            raise ValidationError("An EPARGNE transaction must reference a SavingsGoal.")
        if dto.flow_type not in (FlowType.DETTE,) and dto.debt_id is not None:
            raise ValidationError("Only DETTE transactions can reference a Debt.")
        if dto.flow_type not in (FlowType.EPARGNE,) and dto.goal_id is not None:
            raise ValidationError("Only EPARGNE transactions can reference a SavingsGoal.")
