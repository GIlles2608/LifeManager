"""Mappings between the SQLAlchemy SavingsGoal model and domain entity."""

from __future__ import annotations

from lifemanager.finance.domain.entities import SavingsGoal as SavingsGoalEntity
from lifemanager.finance.models import SavingsGoal


class SavingsGoalMapper:
    """Convert savings-goal persistence rows to and from domain entities."""

    @staticmethod
    def to_entity(model: SavingsGoal) -> SavingsGoalEntity:
        return SavingsGoalEntity(
            id=model.id,
            name=model.name,
            target_amount=model.target_amount,
            current_amount=model.current_amount,
            monthly_target=model.monthly_target,
            target_date=model.target_date,
            status=model.status,
        )

    @staticmethod
    def to_model(entity: SavingsGoalEntity) -> SavingsGoal:
        return SavingsGoal(
            id=entity.id,
            name=entity.name,
            target_amount=entity.target_amount,
            current_amount=entity.current_amount,
            monthly_target=entity.monthly_target,
            target_date=entity.target_date,
            status=entity.status,
        )
