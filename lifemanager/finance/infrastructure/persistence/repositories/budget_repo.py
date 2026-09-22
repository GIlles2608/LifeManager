"""BudgetRepository — DB access for Budget entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from lifemanager.finance.domain.entities import Budget as BudgetEntity
from lifemanager.finance.infrastructure.persistence.mappers import BudgetMapper
from lifemanager.finance.models import Budget


class BudgetRepository:
    model = Budget

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_category_and_month(self, category_id: uuid.UUID, month: str) -> BudgetEntity | None:
        """
        Returns the budget defined for a (category, month) pair, or None if
        no budget exists. Absence of a budget is a normal state (no ceiling),
        not an error.
        """
        stmt = select(Budget).where(
            Budget.category_id == category_id,
            Budget.month == month,
        )
        model = self._session.scalars(stmt).first()
        return BudgetMapper.to_entity(model) if model is not None else None

    def list_by_month(self, month: str) -> list[Budget]:
        stmt = select(Budget).where(Budget.month == month)
        return list(self._session.scalars(stmt))
