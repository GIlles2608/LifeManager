"""Financial transaction domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from lifemanager.finance.domain.enums import SenseType


@dataclass(frozen=True)
class Transaction:
    """An immutable financial movement identified by UUID references."""

    id: uuid.UUID
    date: date
    amount: Decimal
    flow_type: str
    sense: str
    label: str
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    debt_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None

    @property
    def signed_amount(self) -> Decimal:
        """Return a positive inflow or negative outflow amount."""
        return self.amount if self.sense == SenseType.ENTREE.value else -self.amount

    @property
    def month(self) -> str:
        """Return the YYYY-MM month used for reporting."""
        return self.date.strftime("%Y-%m")
