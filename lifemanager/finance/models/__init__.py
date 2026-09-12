"""Finance domain models — re-exported here so callers (and Alembic) only need
to import the package, not individual modules.

Importing this package guarantees every model is registered on Base.metadata.
"""
from __future__ import annotations

from lifemanager.finance.models.account import Account
from lifemanager.finance.models.alert import Alert
from lifemanager.finance.models.budget import Budget
from lifemanager.finance.models.category import Category
from lifemanager.finance.models.debt import Debt
from lifemanager.finance.models.enums import (
    AccountType,
    DebtStatus,
    FlowType,
    GoalStatus,
    GrandType,
    NatureType,
    SenseType,
)
from lifemanager.finance.models.savings_goal import SavingsGoal
from lifemanager.finance.models.transaction import Transaction

__all__ = [
    "Account",
    "AccountType",
    "Alert",
    "Budget",
    "Category",
    "Debt",
    "DebtStatus",
    "FlowType",
    "GoalStatus",
    "GrandType",
    "NatureType",
    "SavingsGoal",
    "SenseType",
    "Transaction",
]
