"""Mappings between the SQLAlchemy Account model and domain entity."""

from __future__ import annotations

from lifemanager.finance.domain.entities import Account as AccountEntity
from lifemanager.finance.models import Account


class AccountMapper:
    """Convert account persistence rows to and from domain entities."""

    @staticmethod
    def to_entity(model: Account) -> AccountEntity:
        return AccountEntity(
            id=model.id,
            name=model.name,
            type=model.type,
            initial_balance=model.initial_balance,
            is_active=model.is_active,
        )

    @staticmethod
    def to_model(entity: AccountEntity) -> Account:
        return Account(
            id=entity.id,
            name=entity.name,
            type=entity.type,
            initial_balance=entity.initial_balance,
            is_active=entity.is_active,
        )
