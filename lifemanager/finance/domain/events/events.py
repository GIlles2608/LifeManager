"""Facts emitted by Finance domain entities."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

from lifemanager.core.ports.event_publisher import DomainEvent

if TYPE_CHECKING:
    from lifemanager.finance.domain.entities import Budget, Debt, Transaction


@dataclass(frozen=True)
class TransactionCreated(DomainEvent):
    """A transaction has been created in the domain."""

    event_name: ClassVar[str] = "transaction.created"
    transaction: Transaction


@dataclass(frozen=True)
class TransactionDeleted(DomainEvent):
    """A transaction has been deleted from the domain."""

    event_name: ClassVar[str] = "transaction.deleted"
    transaction_id: uuid.UUID


@dataclass(frozen=True)
class BudgetExceeded(DomainEvent):
    """A budget ceiling was exceeded by actual spending."""

    event_name: ClassVar[str] = "budget.exceeded"
    budget: Budget
    spent: Decimal


@dataclass(frozen=True)
class DebtUpdated(DomainEvent):
    """A debt balance was updated in the domain."""

    event_name: ClassVar[str] = "debt.updated"
    debt: Debt
