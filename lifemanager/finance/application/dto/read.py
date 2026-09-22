"""Immutable read models exposed above Finance repositories."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class TransactionReadDTO:
    """Transaction data prepared for presentation without ORM relations."""

    id: uuid.UUID
    date: date
    amount: Decimal
    flow_type: str
    sense: str
    label: str
    account_id: uuid.UUID
    account_name: str
    category_id: uuid.UUID | None
    category_name: str | None
    debt_id: uuid.UUID | None
    goal_id: uuid.UUID | None


@dataclass(frozen=True)
class AccountReadDTO:
    """Account data exposed to presentation adapters."""

    id: uuid.UUID
    name: str
    type: str
    initial_balance: Decimal
    is_active: bool


@dataclass(frozen=True)
class CategoryReadDTO:
    """Category data exposed to presentation adapters."""

    id: uuid.UUID
    name: str
    grand_type: str
    nature: str
    is_active: bool
    parent_id: uuid.UUID | None


@dataclass(frozen=True)
class BudgetReadDTO:
    """Budget data exposed to presentation adapters."""

    id: uuid.UUID
    month: str
    ceiling: Decimal
    category_id: uuid.UUID


@dataclass(frozen=True)
class DebtReadDTO:
    """Debt data exposed to presentation adapters."""

    id: uuid.UUID
    name: str
    debt_type: str
    initial_amount: Decimal
    current_balance: Decimal
    monthly_target: Decimal
    status: str
    started_at: date


@dataclass(frozen=True)
class SavingsGoalReadDTO:
    """Savings goal data exposed to presentation adapters."""

    id: uuid.UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    monthly_target: Decimal
    target_date: date
    status: str
