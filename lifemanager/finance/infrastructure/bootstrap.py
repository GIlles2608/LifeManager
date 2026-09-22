"""Composition root for Finance infrastructure adapters."""

from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from lifemanager.finance.domain.ports import (
    AccountRepositoryPort,
    BudgetRepositoryPort,
    CategoryRepositoryPort,
    DebtRepositoryPort,
    SavingsGoalRepositoryPort,
    TransactionRepositoryPort,
)
from lifemanager.finance.infrastructure.persistence.repositories import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    DebtRepository,
    SavingsGoalRepository,
    TransactionRepository,
)
from lifemanager.finance.services.finance_service import FinanceService


def build_finance_service(session: Session) -> FinanceService:
    """Compose concrete persistence adapters for the Finance service."""
    return FinanceService(
        tx_repo=cast(TransactionRepositoryPort, TransactionRepository(session)),
        budget_repo=cast(BudgetRepositoryPort, BudgetRepository(session)),
        category_repo=cast(CategoryRepositoryPort, CategoryRepository(session)),
        debt_repo=cast(DebtRepositoryPort, DebtRepository(session)),
        account_repo=cast(AccountRepositoryPort, AccountRepository(session)),
        goal_repo=cast(SavingsGoalRepositoryPort, SavingsGoalRepository(session)),
    )
