"""BudgetRepository — DB access for Budget entities."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.models import Budget


class BudgetRepository(BaseRepository[Budget]):
    model = Budget

    def get_by_category_and_month(
        self, category_id: uuid.UUID, month: str
    ) -> Budget | None:
        """
        Returns the budget defined for a (category, month) pair, or None if
        no budget exists. Absence of a budget is a normal state (no ceiling),
        not an error.
        """
        stmt = select(Budget).where(
            Budget.category_id == category_id,
            Budget.month == month,
        )
        return self._session.scalars(stmt).first()

    def list_by_month(self, month: str) -> list[Budget]:
        stmt = select(Budget).where(Budget.month == month)
        return list(self._session.scalars(stmt))
