"""DebtRepository — DB access for Debt entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from lifemanager.core.exceptions.exceptions import NotFoundError
from lifemanager.finance.application.dto import DebtReadDTO
from lifemanager.finance.domain.entities import Debt as DebtEntity
from lifemanager.finance.domain.enums import DebtStatus
from lifemanager.finance.infrastructure.persistence.mappers import DebtMapper
from lifemanager.finance.models import Debt


class DebtRepository:
    model = Debt

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, entity_id: uuid.UUID) -> Debt | None:
        """Return the ORM debt row, or None if it doesn't exist."""
        return self._session.get(Debt, entity_id)

    def find_domain_by_id(self, entity_id: uuid.UUID) -> DebtEntity | None:
        """Return a debt as a pure domain entity."""
        model = self.find_by_id(entity_id)
        return DebtMapper.to_entity(model) if model is not None else None

    def save_domain(self, entity: DebtEntity) -> DebtEntity:
        """Persist a domain debt and return the same immutable entity."""
        model = self._session.get(Debt, entity.id)
        if model is None:
            raise NotFoundError("Debt", entity.id)
        model.current_balance = entity.current_balance
        model.status = entity.status
        self._session.flush()
        return entity

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
