"""Immutable Finance domain entities."""

from __future__ import annotations

from lifemanager.finance.domain.entities.account import Account
from lifemanager.finance.domain.entities.budget import Budget
from lifemanager.finance.domain.entities.category import Category
from lifemanager.finance.domain.entities.debt import Debt
from lifemanager.finance.domain.entities.savings_goal import SavingsGoal
from lifemanager.finance.domain.entities.transaction import Transaction

__all__ = ["Account", "Budget", "Category", "Debt", "SavingsGoal", "Transaction"]
