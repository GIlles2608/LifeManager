"""Finance repositories — re-exported for a single import point."""
from __future__ import annotations

from lifemanager.finance.repositories.account_repo import AccountRepository
from lifemanager.finance.repositories.budget_repo import BudgetRepository
from lifemanager.finance.repositories.category_repo import CategoryRepository
from lifemanager.finance.repositories.debt_repo import DebtRepository
from lifemanager.finance.repositories.savings_goal_repo import SavingsGoalRepository
from lifemanager.finance.repositories.transaction_repo import TransactionRepository

__all__ = [
    "AccountRepository",
    "BudgetRepository",
    "CategoryRepository",
    "DebtRepository",
    "SavingsGoalRepository",
    "TransactionRepository",
]
