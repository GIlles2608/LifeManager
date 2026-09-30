"""Financial transaction domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date as Date
from decimal import Decimal
from typing import Self

from lifemanager.core.ports.event_publisher import DomainEvent
from lifemanager.finance.domain.enums import SenseType
from lifemanager.finance.domain.events import TransactionCreated, TransactionDeleted


@dataclass(frozen=True)
class Transaction:
    """An immutable financial movement identified by UUID references."""

    id: uuid.UUID
    date: Date
    amount: Decimal
    flow_type: str
    sense: str
    label: str
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    debt_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    _events: list[DomainEvent] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    @classmethod
    def create(
        cls,
        *,
        id: uuid.UUID,
        date: Date,
        amount: Decimal,
        flow_type: str,
        sense: str,
        label: str,
        account_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
        debt_id: uuid.UUID | None = None,
        goal_id: uuid.UUID | None = None,
    ) -> Self:
        """Create a transaction and record its domain fact."""
        transaction = cls(
            id=id,
            date=date,
            amount=amount,
            flow_type=flow_type,
            sense=sense,
            label=label,
            account_id=account_id,
            category_id=category_id,
            debt_id=debt_id,
            goal_id=goal_id,
        )
        transaction._events.append(TransactionCreated(transaction))
        return transaction

    def mark_deleted(self) -> None:
        """Record that this transaction is about to be deleted."""
        self._events.append(TransactionDeleted(self.id))

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear facts waiting to be published."""
        events = list(self._events)
        self._events.clear()
        return events

    @property
    def signed_amount(self) -> Decimal:
        """Return a positive inflow or negative outflow amount."""
        return self.amount if self.sense == SenseType.ENTREE.value else -self.amount

    @property
    def month(self) -> str:
        """Return the YYYY-MM month used for reporting."""
        return self.date.strftime("%Y-%m")
