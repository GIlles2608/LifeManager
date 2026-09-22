from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from lifemanager.finance.domain.entities import Transaction as TransactionEntity
from lifemanager.finance.infrastructure.persistence.mappers import TransactionMapper


def test_transaction_mapper_round_trips_without_relations() -> None:
    entity = TransactionEntity(
        id=uuid.uuid4(),
        date=date(2026, 9, 22),
        amount=Decimal("42.50"),
        flow_type="depense",
        sense="sortie",
        label="Courses",
        account_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
    )

    model = TransactionMapper.to_model(entity)
    result = TransactionMapper.to_entity(model)

    assert result == entity
    assert model.account_id == entity.account_id
    assert model.category_id == entity.category_id
