from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from lifemanager.finance.domain.entities import Account, Category, SavingsGoal
from lifemanager.finance.infrastructure.persistence.mappers import (
    AccountMapper,
    CategoryMapper,
    SavingsGoalMapper,
)


@pytest.mark.parametrize(
    ("entity", "mapper"),
    [
        (
            Account(uuid.uuid4(), "Courant", "courant", Decimal(100), True),
            AccountMapper,
        ),
        (
            Category(uuid.uuid4(), "Courses", "depense", "variable", True, None),
            CategoryMapper,
        ),
        (
            SavingsGoal(
                uuid.uuid4(),
                "Voyage",
                Decimal(1200),
                Decimal(300),
                Decimal(100),
                date(2026, 12, 1),
                "actif",
            ),
            SavingsGoalMapper,
        ),
    ],
)
def test_reference_mapper_round_trips(entity, mapper) -> None:
    assert mapper.to_entity(mapper.to_model(entity)) == entity
