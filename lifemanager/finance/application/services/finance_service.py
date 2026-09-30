"""Application service for Finance operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from lifemanager.core.exceptions.exceptions import NotFoundError
from lifemanager.finance.application.dto import (
    AccountReadDTO,
    CategoryReadDTO,
    DebtReadDTO,
    SavingsGoalReadDTO,
    TransactionDTO,
    TransactionReadDTO,
)
from lifemanager.finance.application.ports import AbstractUnitOfWork, UnitOfWorkFactory
from lifemanager.finance.domain.entities import Transaction as TransactionEntity
from lifemanager.finance.domain.enums import FlowType
from lifemanager.finance.domain.exceptions import ValidationError


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


class FinanceService:
    """Application facade for Finance use cases.

    Each public method opens its own unit of work through the injected
    factory, so one user action maps to one transaction: it commits when the
    method returns and rolls back if it raises. Helpers prefixed with an
    underscore take the active unit of work as their first argument and never
    open one themselves — that is what lets a method such as
    ``create_transaction`` reuse ``_check_budget`` inside its own transaction.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def create_transaction(self, dto: TransactionDTO) -> TransactionReadDTO:
        """Validate, persist, and check the budget if applicable."""
        self._validate_transaction(dto)
        tx = TransactionEntity.create(
            id=uuid.uuid4(),
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
        with self._uow_factory() as uow:
            uow.tx_repo.add(tx)
            if dto.flow_type == FlowType.DEPENSE and dto.category_id is not None:
                self._check_budget(uow, dto.category_id, tx.month, record_event=True)
            read_dto = uow.tx_repo.read_by_id(tx.id)
            if read_dto is None:
                raise NotFoundError("Transaction", tx.id)

        return read_dto

    def delete_transaction(self, transaction_id: uuid.UUID) -> None:
        """Delete a transaction by id."""
        with self._uow_factory() as uow:
            uow.tx_repo.delete(transaction_id)

    def list_transactions(self, month: str) -> list[TransactionReadDTO]:
        """Return immutable, presentation-ready transactions for the month."""
        with self._uow_factory() as uow:
            return uow.tx_repo.list_by_month_with_relations(month)

    def list_accounts(self) -> list[AccountReadDTO]:
        """Return all active accounts as read DTOs."""
        with self._uow_factory() as uow:
            return uow.account_repo.list_active_read()

    def list_categories(self) -> list[CategoryReadDTO]:
        """Return all active categories as read DTOs."""
        with self._uow_factory() as uow:
            return uow.category_repo.list_active_read()

    def list_active_debts(self) -> list[DebtReadDTO]:
        """Return all active debts as read DTOs."""
        with self._uow_factory() as uow:
            return uow.debt_repo.list_active_read()

    def list_active_goals(self) -> list[SavingsGoalReadDTO]:
        """Return all active savings goals as read DTOs."""
        with self._uow_factory() as uow:
            return uow.goal_repo.list_active_read()

    def check_budget(self, category_id: uuid.UUID, month: str) -> BudgetCheckResult:
        """Compare actual spending with the budget ceiling."""
        with self._uow_factory() as uow:
            return self._check_budget(uow, category_id, month)

    def get_monthly_kpis(self, month: str) -> MonthlyKPIs:
        """Return the five headline KPIs for a month."""
        with self._uow_factory() as uow:
            revenues = uow.tx_repo.total_by_flow(FlowType.REVENU, month)
            expenses = uow.tx_repo.total_by_flow(FlowType.DEPENSE, month)
            savings = uow.tx_repo.total_by_flow(FlowType.EPARGNE, month)
            debts = uow.tx_repo.total_by_flow(FlowType.DETTE, month)
        return MonthlyKPIs(
            month=month,
            revenues=revenues,
            expenses=expenses,
            savings=savings,
            debt_repayments=debts,
            net=revenues - expenses - savings - debts,
        )

    def update_debt_balance(self, debt_id: uuid.UUID, new_balance: Decimal) -> None:
        """Update a debt balance immutably."""
        if new_balance < 0:
            raise ValidationError("Debt balance cannot be negative.")
        with self._uow_factory() as uow:
            debt = uow.debt_repo.find_domain_by_id(debt_id)
            if debt is None:
                raise NotFoundError("Debt", debt_id)
            updated_debt = debt.update_balance(new_balance)
            uow.debt_repo.save_domain(updated_debt)

    def _check_budget(
        self,
        uow: AbstractUnitOfWork,
        category_id: uuid.UUID,
        month: str,
        *,
        record_event: bool = False,
    ) -> BudgetCheckResult:
        """Budget comparison running inside an already-open unit of work."""
        budget = uow.budget_repo.get_by_category_and_month(category_id, month)
        category = uow.category_repo.find_read_by_id(category_id)
        ceiling = budget.ceiling if budget is not None else Decimal(0)
        spent = uow.tx_repo.total_spent_by_category(category_id, month)
        remaining = ceiling - spent
        result = BudgetCheckResult(
            category_name=category.name if category is not None else "Inconnu",
            ceiling=ceiling,
            spent=spent,
            remaining=max(remaining, Decimal(0)),
            is_exceeded=ceiling > 0 and spent > ceiling,
        )
        if record_event and budget is not None and result.is_exceeded:
            budget.record_exceeded(spent)
        return result

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
