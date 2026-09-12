"""Category model — self-referencing, max depth 2."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel
from lifemanager.finance.models.enums import NatureType

if TYPE_CHECKING:
    from lifemanager.finance.models.budget import Budget
    from lifemanager.finance.models.transaction import Transaction


class Category(BaseModel):
    __tablename__ = "category"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    grand_type: Mapped[str] = mapped_column(String(30), nullable=False)
    nature: Mapped[str] = mapped_column(String(20), nullable=False, default=NatureType.VARIABLE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id"), nullable=True
    )

    parent: Mapped["Category | None"] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="category"
    )
    budgets: Mapped[list[Budget]] = relationship(
        "Budget", back_populates="category"
    )
