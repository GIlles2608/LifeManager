"""Monthly budget domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from lifemanager.core.ports.event_publisher import DomainEvent
from lifemanager.finance.domain.events import BudgetExceeded


@dataclass(frozen=True)
class Budget:
    """Spending ceiling for one category and month."""

    id: uuid.UUID
    month: str
    ceiling: Decimal
    category_id: uuid.UUID
    _events: list[DomainEvent] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    def record_exceeded(self, spent: Decimal) -> None:
        """Record a budget-exceeded fact when spending crosses the ceiling."""
        if self.ceiling > 0 and spent > self.ceiling:
            self._events.append(BudgetExceeded(self, spent))

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear facts waiting to be published."""
        events = list(self._events)
        self._events.clear()
        return events
