from __future__ import annotations

import uuid
from decimal import Decimal

from lifemanager.finance.domain.entities import Account, Budget, Category


def test_account_category_and_budget_are_frozen_data_objects() -> None:
    account = Account(uuid.uuid4(), "Courant", "courant", Decimal(100), True)
    category = Category(uuid.uuid4(), "Alimentation", "depense", "variable", True, None)
    budget = Budget(uuid.uuid4(), "2026-09", Decimal(300), category.id)

    assert account.name == "Courant"
    assert category.parent_id is None
    assert budget.category_id == category.id
    assert account != category
