"""Savings goal domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class SavingsGoal:
    """An immutable savings target and its current progress."""

    id: uuid.UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    monthly_target: Decimal
    target_date: date
    status: str

    @property
    def remaining(self) -> Decimal:
        """Return the amount still needed to reach the target."""
        return self.target_amount - self.current_amount

    @property
    def progress(self) -> float:
        """Return savings progress between zero and one."""
        if self.target_amount == 0:
            return 0.0
        return float(self.current_amount / self.target_amount)
