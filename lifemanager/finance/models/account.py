"""Account model — bank account, savings account, cash, etc."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel
from lifemanager.finance.models.enums import AccountType

if TYPE_CHECKING:
    from lifemanager.finance.models.transaction import Transaction


class Account(BaseModel):
    __tablename__ = "account"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default=AccountType.COURANT)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="account", lazy="select"
    )
