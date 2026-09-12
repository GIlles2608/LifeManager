"""SavingsGoal model — a target amount to save by a given date."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel
from lifemanager.finance.models.enums import GoalStatus

if TYPE_CHECKING:
    from lifemanager.finance.models.transaction import Transaction


class SavingsGoal(BaseModel):
    __tablename__ = "savings_goal"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    monthly_target: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=GoalStatus.ACTIF)

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="goal"
    )

    @property
    def remaining(self) -> Decimal:
        return self.target_amount - self.current_amount

    @property
    def progress(self) -> float:
        if self.target_amount == 0:
            return 0.0
        return float(self.current_amount / self.target_amount)
