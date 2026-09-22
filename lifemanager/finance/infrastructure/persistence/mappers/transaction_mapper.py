"""Mapping between the Transaction ORM row and domain entity."""

from __future__ import annotations

from lifemanager.finance.domain.entities import Transaction as TransactionEntity
from lifemanager.finance.models.transaction import Transaction as TransactionModel


class TransactionMapper:
    """Convert transaction persistence rows without leaking ORM types upward."""

    @staticmethod
    def to_entity(model: TransactionModel) -> TransactionEntity:
        return TransactionEntity(
            id=model.id,
            date=model.date,
            amount=model.amount,
            flow_type=model.flow_type,
            sense=model.sense,
            label=model.label,
            account_id=model.account_id,
            category_id=model.category_id,
            debt_id=model.debt_id,
            goal_id=model.goal_id,
        )

    @staticmethod
    def to_model(entity: TransactionEntity) -> TransactionModel:
        return TransactionModel(
            id=entity.id,
            date=entity.date,
            amount=entity.amount,
            flow_type=entity.flow_type,
            sense=entity.sense,
            label=entity.label,
            account_id=entity.account_id,
            category_id=entity.category_id,
            debt_id=entity.debt_id,
            goal_id=entity.goal_id,
        )
