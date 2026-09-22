"""Unit tests for the transaction table's DTO presentation contract."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from PyQt6.QtCore import Qt

from lifemanager.core.utils.formatting import format_amount
from lifemanager.finance.application.dto import TransactionReadDTO
from lifemanager.finance.models import SenseType
from lifemanager.finance.views.transaction_table_model import TransactionTableModel


def make_transaction(**overrides: object) -> TransactionReadDTO:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "date": date(2026, 5, 3),
        "amount": Decimal("42.50"),
        "flow_type": "depense",
        "sense": SenseType.SORTIE.value,
        "label": "Courses",
        "account_id": uuid.uuid4(),
        "account_name": "Compte courant",
        "category_id": uuid.uuid4(),
        "category_name": "Alimentation",
        "debt_id": None,
        "goal_id": None,
    }
    values.update(overrides)
    return TransactionReadDTO(**values)


def test_table_model_renders_flattened_transaction_dto(qtbot) -> None:
    model = TransactionTableModel()
    model.set_transactions([make_transaction()])

    assert model.rowCount() == 1
    assert model.data(model.index(0, model.COL_LABEL), Qt.ItemDataRole.DisplayRole) == "Courses"
    assert (
        model.data(model.index(0, model.COL_CATEGORY), Qt.ItemDataRole.DisplayRole)
        == "Alimentation"
    )
    assert (
        model.data(model.index(0, model.COL_ACCOUNT), Qt.ItemDataRole.DisplayRole)
        == "Compte courant"
    )
    assert model.data(
        model.index(0, model.COL_AMOUNT), Qt.ItemDataRole.DisplayRole
    ) == format_amount(Decimal("-42.50"))


def test_table_model_uses_placeholder_for_missing_category() -> None:
    model = TransactionTableModel()
    transaction = make_transaction(category_id=None, category_name=None)
    model.set_transactions([transaction])

    assert model.data(model.index(0, model.COL_CATEGORY), Qt.ItemDataRole.DisplayRole) == "—"
    assert model.transaction_at(0) is transaction
    assert model.transaction_at(1) is None
