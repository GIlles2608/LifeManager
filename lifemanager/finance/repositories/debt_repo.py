"""DebtRepository — DB access for Debt entities."""

from __future__ import annotations

from sqlalchemy import select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.application.dto import DebtReadDTO
from lifemanager.finance.models import Debt, DebtStatus


class DebtRepository(BaseRepository[Debt]):
    model = Debt

    def list_active(self) -> list[Debt]:
        stmt = select(Debt).where(Debt.status == DebtStatus.ACTIVE.value).order_by(Debt.started_at)
        return list(self._session.scalars(stmt))

    def list_active_read(self) -> list[DebtReadDTO]:
        """Return active debts without exposing ORM instances."""
        return [self._to_read_dto(debt) for debt in self.list_active()]

    @staticmethod
    def _to_read_dto(debt: Debt) -> DebtReadDTO:
        return DebtReadDTO(
            id=debt.id,
            name=debt.name,
            debt_type=debt.debt_type,
            initial_amount=debt.initial_amount,
            current_balance=debt.current_balance,
            monthly_target=debt.monthly_target,
            status=debt.status,
            started_at=debt.started_at,
        )
