"""DebtRepository — DB access for Debt entities."""
from __future__ import annotations

from sqlalchemy import select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.models import Debt, DebtStatus


class DebtRepository(BaseRepository[Debt]):
    model = Debt

    def list_active(self) -> list[Debt]:
        stmt = (
            select(Debt)
            .where(Debt.status == DebtStatus.ACTIVE.value)
            .order_by(Debt.started_at)
        )
        return list(self._session.scalars(stmt))
