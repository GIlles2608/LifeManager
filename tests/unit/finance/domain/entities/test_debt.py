from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from lifemanager.finance.domain.entities import Debt


def make_debt(**overrides: object) -> Debt:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Pret",
        "debt_type": "personnel",
        "initial_amount": Decimal(1000),
        "current_balance": Decimal(750),
        "monthly_target": Decimal(100),
        "status": "active",
        "started_at": date(2026, 1, 1),
    }
    values.update(overrides)
    return Debt(**values)  # type: ignore[arg-type]


def test_debt_calculates_repaid_and_progress() -> None:
    debt = make_debt()

    assert debt.repaid == Decimal(250)
    assert debt.progress == 0.25


def test_record_payment_returns_new_debt_without_mutating_original() -> None:
    debt = make_debt()

    updated = debt.record_payment(Decimal(100))

    assert updated is not debt
    assert debt.current_balance == Decimal(750)
    assert updated.current_balance == Decimal(650)


def test_record_payment_clamps_balance_to_zero() -> None:
    assert make_debt().record_payment(Decimal(900)).current_balance == Decimal(0)


def test_record_payment_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="negative"):
        make_debt().record_payment(Decimal(-1))
