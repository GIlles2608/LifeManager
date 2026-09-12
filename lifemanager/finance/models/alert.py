"""Alert model — user-facing notifications (e.g. budget exceeded)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifemanager.core.models.base import BaseModel

if TYPE_CHECKING:
    from lifemanager.finance.models.budget import Budget


class Alert(BaseModel):
    __tablename__ = "alert"

    alert_type: Mapped[str] = mapped_column(String(60), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    budget_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budget.id"), nullable=True
    )
    budget: Mapped[Budget | None] = relationship("Budget", back_populates="alerts")
