"""Budget model — monthly spending ceiling per category."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel

if TYPE_CHECKING:
    from lifemanager.finance.models.alert import Alert
    from lifemanager.finance.models.category import Category


class Budget(BaseModel):
    __tablename__ = "budget"

    month: Mapped[str] = mapped_column(String(7), nullable=False)   # YYYY-MM
    ceiling: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id"), nullable=False
    )
    category: Mapped[Category] = relationship("Category", back_populates="budgets")
    alerts: Mapped[list[Alert]] = relationship("Alert", back_populates="budget")
