"""AccountRepository — DB access for Account entities."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from lifemanager.finance.application.dto import AccountReadDTO
from lifemanager.finance.domain.enums import SenseType
from lifemanager.finance.models import Account, Transaction


class AccountRepository:
    model = Account

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, entity_id: uuid.UUID) -> Account | None:
        """Return the ORM account row, or None if it doesn't exist."""
        return self._session.get(Account, entity_id)

    def list_active(self) -> list[Account]:
        stmt = select(Account).where(Account.is_active.is_(True)).order_by(Account.name)
        return list(self._session.scalars(stmt))

    def list_active_read(self) -> list[AccountReadDTO]:
        """Return active accounts without exposing ORM instances."""
        return [self._to_read_dto(account) for account in self.list_active()]

    @staticmethod
    def _to_read_dto(account: Account) -> AccountReadDTO:
        return AccountReadDTO(
            id=account.id,
            name=account.name,
            type=account.type,
            initial_balance=account.initial_balance,
            is_active=account.is_active,
        )

    def get_balance(self, account_id: uuid.UUID) -> Decimal:
        """
        Current balance = initial_balance + Σ signed transactions, computed in SQL.
        Returns Decimal('0') for an unknown account_id (no rows match).
        """
        account = self.find_by_id(account_id)
        if account is None:
            return Decimal(0)

        signed = case(
            (Transaction.sense == SenseType.ENTREE.value, Transaction.amount),
            else_=-Transaction.amount,
        )
        stmt = select(func.coalesce(func.sum(signed), 0)).where(
            Transaction.account_id == account_id
        )
        delta = self._session.scalar(stmt) or 0
        return account.initial_balance + Decimal(str(delta))
