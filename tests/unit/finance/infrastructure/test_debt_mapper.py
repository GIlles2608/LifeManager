from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from lifemanager.finance.domain.entities import Debt as DebtEntity
from lifemanager.finance.infrastructure.persistence.mappers import DebtMapper


def test_debt_mapper_round_trips_without_transactions() -> None:
    entity = DebtEntity(
        id=uuid.uuid4(),
        name="Pret",
        debt_type="personnel",
        initial_amount=Decimal(1000),
        current_balance=Decimal(750),
        monthly_target=Decimal(100),
        status="active",
        started_at=date(2026, 1, 1),
    )

    model = DebtMapper.to_model(entity)
    result = DebtMapper.to_entity(model)

    assert result == entity
    assert model.current_balance == entity.current_balance
