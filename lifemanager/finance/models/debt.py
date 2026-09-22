"""Debt model — tracks an outstanding debt and its repayment progress."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel
from lifemanager.finance.domain.enums import DebtStatus

if TYPE_CHECKING:
    from lifemanager.finance.models.transaction import Transaction


class Debt(BaseModel):
    __tablename__ = "debt"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    debt_type: Mapped[str] = mapped_column(String(60), nullable=False)
    initial_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monthly_target: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DebtStatus.ACTIVE)
    started_at: Mapped[date] = mapped_column(Date, nullable=False)

    transactions: Mapped[list[Transaction]] = relationship("Transaction", back_populates="debt")
