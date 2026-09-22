"""Transaction model — atomic financial movement."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel

if TYPE_CHECKING:
    from lifemanager.finance.models.account import Account
    from lifemanager.finance.models.category import Category
    from lifemanager.finance.models.debt import Debt
    from lifemanager.finance.models.savings_goal import SavingsGoal


class Transaction(BaseModel):
    __tablename__ = "transaction"

    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    flow_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sense: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id"), nullable=True
    )
    debt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debt.id"), nullable=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("savings_goal.id"), nullable=True
    )

    account: Mapped[Account] = relationship("Account", back_populates="transactions")
    category: Mapped[Category | None] = relationship("Category", back_populates="transactions")
    debt: Mapped[Debt | None] = relationship("Debt", back_populates="transactions")
    goal: Mapped[SavingsGoal | None] = relationship("SavingsGoal", back_populates="transactions")
