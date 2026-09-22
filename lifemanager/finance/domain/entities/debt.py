"""Debt domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Debt:
    """An immutable debt with repayment progress."""

    id: uuid.UUID
    name: str
    debt_type: str
    initial_amount: Decimal
    current_balance: Decimal
    monthly_target: Decimal
    status: str
    started_at: date

    @property
    def repaid(self) -> Decimal:
        """Return the amount repaid so far."""
        return self.initial_amount - self.current_balance

    @property
    def progress(self) -> float:
        """Return repayment progress between zero and one."""
        if self.initial_amount == 0:
            return 0.0
        return float(self.repaid / self.initial_amount)

    def record_payment(self, amount: Decimal) -> Debt:
        """Return a new debt with a payment applied to its balance."""
        if amount < 0:
            raise ValueError("Payment amount cannot be negative.")
        return Debt(
            id=self.id,
            name=self.name,
            debt_type=self.debt_type,
            initial_amount=self.initial_amount,
            current_balance=max(self.current_balance - amount, Decimal(0)),
            monthly_target=self.monthly_target,
            status=self.status,
            started_at=self.started_at,
        )
