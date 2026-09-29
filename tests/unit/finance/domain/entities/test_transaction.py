from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from lifemanager.finance.domain.entities import Transaction
from lifemanager.finance.domain.enums import SenseType


def test_transaction_calculates_signed_amount_and_month() -> None:
    transaction = Transaction(
        id=uuid.uuid4(),
        date=date(2026, 9, 22),
        amount=Decimal("42.50"),
        flow_type="depense",
        sense=SenseType.SORTIE.value,
        label="Courses",
        account_id=uuid.uuid4(),
    )

    assert transaction.signed_amount == Decimal("-42.50")
    assert transaction.month == "2026-09"


def test_transaction_is_immutable() -> None:
    transaction = Transaction(
        id=uuid.uuid4(),
        date=date(2026, 9, 22),
        amount=Decimal(10),
        flow_type="revenu",
        sense=SenseType.ENTREE.value,
        label="Salaire",
        account_id=uuid.uuid4(),
    )

    with pytest.raises(AttributeError):
        cast(Any, transaction).label = "Autre"
