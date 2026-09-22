from __future__ import annotations

import uuid
from decimal import Decimal

from lifemanager.finance.domain.entities import Budget as BudgetEntity
from lifemanager.finance.infrastructure.persistence.mappers import BudgetMapper


def test_budget_mapper_round_trips() -> None:
    entity = BudgetEntity(
        id=uuid.uuid4(),
        month="2026-05",
        ceiling=Decimal("250.00"),
        category_id=uuid.uuid4(),
    )

    model = BudgetMapper.to_model(entity)

    assert BudgetMapper.to_entity(model) == entity