"""Shared fixtures for finance integration tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from lifemanager.finance.models import (
    Account,
    AccountType,
    Category,
    FlowType,
    GrandType,
    SenseType,
    Transaction,
)


@pytest.fixture
def account(db_session: Session) -> Account:
    acc = Account(name="Compte courant", type=AccountType.COURANT, initial_balance=Decimal(0))
    db_session.add(acc)
    db_session.flush()
    return acc


@pytest.fixture
def category(db_session: Session) -> Category:
    cat = Category(name="Alimentation", grand_type=GrandType.DEPENSE)
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def make_transaction(db_session: Session, account: Account) -> Callable[..., Transaction]:
    """Factory for a `Transaction` tied to the default `account` fixture."""

    def _make(
        *,
        day: date,
        amount: str,
        sense: SenseType,
        flow_type: FlowType,
        category: Category | None = None,
        label: str = "tx",
        account_override: Account | None = None,
    ) -> Transaction:
        tx = Transaction(
            date=day,
            amount=Decimal(amount),
            sense=sense.value,
            flow_type=flow_type.value,
            label=label,
            account_id=(account_override or account).id,
            category_id=category.id if category else None,
        )
        db_session.add(tx)
        db_session.flush()
        return tx

    return _make
