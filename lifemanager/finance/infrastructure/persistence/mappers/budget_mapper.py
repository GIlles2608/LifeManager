"""Mappings between the SQLAlchemy Budget model and domain entity."""

from __future__ import annotations

from lifemanager.finance.domain.entities import Budget as BudgetEntity
from lifemanager.finance.models import Budget


class BudgetMapper:
    """Convert budget persistence rows to and from domain entities."""

    @staticmethod
    def to_entity(model: Budget) -> BudgetEntity:
        return BudgetEntity(
            id=model.id,
            month=model.month,
            ceiling=model.ceiling,
            category_id=model.category_id,
        )

    @staticmethod
    def to_model(entity: BudgetEntity) -> Budget:
        return Budget(
            id=entity.id,
            month=entity.month,
            ceiling=entity.ceiling,
            category_id=entity.category_id,
        )