"""Integration tests for AccountRepository (list_active, get_balance)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from lifemanager.finance.models import Account, AccountType, FlowType, SenseType
from lifemanager.finance.infrastructure.persistence.repositories.account_repo import AccountRepository


@pytest.fixture
def repo(db_session) -> AccountRepository:
    return AccountRepository(db_session)


class TestListActive:
    def test_returns_only_active_accounts(self, db_session, repo, account):
        inactive = Account(
            name="Compte fermé",
            type=AccountType.COURANT,
            initial_balance=Decimal(0),
            is_active=False,
        )
        db_session.add(inactive)
        db_session.flush()

        result = repo.list_active()

        assert account.id in {acc.id for acc in result}
        assert inactive.id not in {acc.id for acc in result}

    def test_orders_by_name(self, db_session, repo, account):
        # `account` fixture is named "Compte courant".
        db_session.add_all(
            [
                Account(name="Zorro", type=AccountType.COURANT, initial_balance=Decimal(0)),
                Account(name="Alpha", type=AccountType.COURANT, initial_balance=Decimal(0)),
            ]
        )
        db_session.flush()

        names = [acc.name for acc in repo.list_active()]

        assert names == sorted(names)


class TestGetBalance:
    def test_equals_initial_balance_when_no_transactions(self, db_session, repo):
        acc = Account(name="Vide", type=AccountType.COURANT, initial_balance=Decimal(100))
        db_session.add(acc)
        db_session.flush()

        assert repo.get_balance(acc.id) == Decimal(100)

    def test_adds_entree_and_subtracts_sortie(self, repo, make_transaction, account):
        make_transaction(
            day=date(2026, 3, 1), amount="50", sense=SenseType.ENTREE, flow_type=FlowType.REVENU
        )
        make_transaction(
            day=date(2026, 3, 2), amount="20", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.get_balance(account.id) == account.initial_balance + Decimal(30)

    def test_unknown_account_id_returns_zero(self, repo):
        assert repo.get_balance(uuid.uuid4()) == Decimal(0)

    def test_ignores_transactions_of_other_accounts(
        self, db_session, repo, make_transaction, account
    ):
        other = Account(name="Autre compte", type=account.type, initial_balance=Decimal(0))
        db_session.add(other)
        db_session.flush()

        make_transaction(
            day=date(2026, 3, 1),
            amount="500",
            sense=SenseType.ENTREE,
            flow_type=FlowType.REVENU,
            account_override=other,
        )

        assert repo.get_balance(account.id) == account.initial_balance
