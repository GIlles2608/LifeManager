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
from lifemanager.finance.repositories import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    DebtRepository,
    SavingsGoalRepository,
    TransactionRepository,
)
from lifemanager.finance.services.finance_service import FinanceService


def build_finance_service(session: Session) -> FinanceService:
    """Factory that composes concrete SQLAlchemy repositories and injects
    them into `FinanceService`. This is the single place that knows about
    `Session` and concrete repository implementations.
    """
    tx_repo = cast(TransactionRepositoryPort, TransactionRepository(session))
    budget_repo = cast(BudgetRepositoryPort, BudgetRepository(session))
    category_repo = cast(CategoryRepositoryPort, CategoryRepository(session))
    debt_repo = cast(DebtRepositoryPort, DebtRepository(session))
    account_repo = cast(AccountRepositoryPort, AccountRepository(session))
    goal_repo = cast(SavingsGoalRepositoryPort, SavingsGoalRepository(session))

    return FinanceService(
        tx_repo=tx_repo,
        budget_repo=budget_repo,
        category_repo=category_repo,
        debt_repo=debt_repo,
        account_repo=account_repo,
        goal_repo=goal_repo,
    )
