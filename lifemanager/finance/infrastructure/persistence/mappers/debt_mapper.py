"""Mapping between the Debt ORM row and domain entity."""

from __future__ import annotations

from lifemanager.finance.domain.entities import Debt as DebtEntity
from lifemanager.finance.models.debt import Debt as DebtModel


class DebtMapper:
    """Convert debt persistence rows without exposing ORM objects to services."""

    @staticmethod
    def to_entity(model: DebtModel) -> DebtEntity:
        return DebtEntity(
            id=model.id,
            name=model.name,
            debt_type=model.debt_type,
            initial_amount=model.initial_amount,
            current_balance=model.current_balance,
            monthly_target=model.monthly_target,
            status=model.status,
            started_at=model.started_at,
        )

    @staticmethod
    def to_model(entity: DebtEntity) -> DebtModel:
        return DebtModel(
            id=entity.id,
            name=entity.name,
            debt_type=entity.debt_type,
            initial_amount=entity.initial_amount,
            current_balance=entity.current_balance,
            monthly_target=entity.monthly_target,
            status=entity.status,
            started_at=entity.started_at,
        )
