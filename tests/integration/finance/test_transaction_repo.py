"""Integration tests for TransactionRepository — the SQL-heaviest repo
(func.to_char monthly grouping, sense/flow_type aggregations).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from lifemanager.finance.models import Account, FlowType, SenseType
from lifemanager.finance.repositories.transaction_repo import TransactionRepository


@pytest.fixture
def repo(db_session) -> TransactionRepository:
    return TransactionRepository(db_session)


# ── Simple reads ──────────────────────────────────────────────────────────────


class TestListByMonth:
    def test_returns_only_transactions_of_the_given_month(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 15), amount="10", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )
        make_transaction(
            day=date(2026, 4, 1), amount="20", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        result = repo.list_by_month("2026-03")

        assert [tx.amount for tx in result] == [Decimal(10)]

    def test_orders_by_date_descending(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1),
            amount="1",
            sense=SenseType.SORTIE,
            flow_type=FlowType.DEPENSE,
            label="early",
        )
        make_transaction(
            day=date(2026, 3, 20),
            amount="2",
            sense=SenseType.SORTIE,
            flow_type=FlowType.DEPENSE,
            label="late",
        )

        result = repo.list_by_month("2026-03")

        assert [tx.label for tx in result] == ["late", "early"]

    def test_respects_year_boundary(self, repo, make_transaction):
        make_transaction(
            day=date(2025, 12, 31), amount="1", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )
        make_transaction(
            day=date(2026, 1, 1), amount="2", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert len(repo.list_by_month("2025-12")) == 1
        assert len(repo.list_by_month("2026-01")) == 1

    def test_empty_month_returns_empty_list(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1), amount="1", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.list_by_month("2026-06") == []


class TestListByMonthWithRelations:
    def test_eager_loads_account_and_category(self, repo, make_transaction, account, category):
        make_transaction(
            day=date(2026, 3, 1),
            amount="10",
            sense=SenseType.SORTIE,
            flow_type=FlowType.DEPENSE,
            category=category,
        )

        result = repo.list_by_month_with_relations("2026-03")

        assert result[0].account.name == account.name
        assert result[0].category is not None
        assert result[0].category.name == category.name


class TestListByAccount:
    def test_returns_only_transactions_of_that_account(
        self, db_session, repo, make_transaction, account
    ):
        other_account = Account(name="Autre compte", type=account.type, initial_balance=Decimal(0))
        db_session.add(other_account)
        db_session.flush()

        make_transaction(
            day=date(2026, 3, 1), amount="10", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )
        make_transaction(
            day=date(2026, 3, 2),
            amount="20",
            sense=SenseType.SORTIE,
            flow_type=FlowType.DEPENSE,
            account_override=other_account,
        )

        result = repo.list_by_account(account.id)

        assert len(result) == 1
        assert result[0].amount == Decimal(10)


# ── Monthly aggregates (critical Postgres SQL) ────────────────────────────────


class TestTotalIn:
    def test_sums_only_entree_transactions(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1), amount="100", sense=SenseType.ENTREE, flow_type=FlowType.REVENU
        )
        make_transaction(
            day=date(2026, 3, 2), amount="30", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_in("2026-03") == Decimal(100)

    def test_ignores_other_months(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 2, 1), amount="100", sense=SenseType.ENTREE, flow_type=FlowType.REVENU
        )

        assert repo.total_in("2026-03") == Decimal(0)


class TestTotalOut:
    def test_sums_only_sortie_transactions(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1), amount="100", sense=SenseType.ENTREE, flow_type=FlowType.REVENU
        )
        make_transaction(
            day=date(2026, 3, 2), amount="30", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_out("2026-03") == Decimal(30)


class TestTotalByFlow:
    def test_sums_regardless_of_sense(self, repo, make_transaction):
        # EPARGNE can be recorded as a SORTIE (transfer out) — total_by_flow ignores sense.
        make_transaction(
            day=date(2026, 3, 1), amount="50", sense=SenseType.SORTIE, flow_type=FlowType.EPARGNE
        )
        make_transaction(
            day=date(2026, 3, 2), amount="20", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_by_flow(FlowType.EPARGNE, "2026-03") == Decimal(50)

    def test_flow_type_with_no_matches_returns_zero(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1), amount="50", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_by_flow(FlowType.DETTE, "2026-03") == Decimal(0)


class TestTotalSpentByCategory:
    def test_sums_depense_transactions_for_the_category(self, repo, make_transaction, category):
        make_transaction(
            day=date(2026, 3, 1),
            amount="15",
            sense=SenseType.SORTIE,
            flow_type=FlowType.DEPENSE,
            category=category,
        )
        make_transaction(
            day=date(2026, 3, 2), amount="99", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_spent_by_category(category.id, "2026-03") == Decimal(15)

    def test_category_with_no_transactions_returns_zero(self, repo, category):
        assert repo.total_spent_by_category(category.id, "2026-03") == Decimal(0)


class TestCashflow:
    def test_is_total_in_minus_total_out(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1), amount="100", sense=SenseType.ENTREE, flow_type=FlowType.REVENU
        )
        make_transaction(
            day=date(2026, 3, 2), amount="40", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.cashflow("2026-03") == Decimal(60)

    def test_negative_when_outflows_exceed_inflows(self, repo, make_transaction):
        make_transaction(
            day=date(2026, 3, 1), amount="10", sense=SenseType.ENTREE, flow_type=FlowType.REVENU
        )
        make_transaction(
            day=date(2026, 3, 2), amount="40", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.cashflow("2026-03") == Decimal(-30)

    def test_ignores_flow_type_uses_sense_only(self, repo, make_transaction):
        # A DETTE repayment tagged as SORTIE must still count against cashflow.
        make_transaction(
            day=date(2026, 3, 1), amount="25", sense=SenseType.SORTIE, flow_type=FlowType.DETTE
        )

        assert repo.cashflow("2026-03") == Decimal(-25)


# ── Edge cases ─────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_month_with_no_transactions_at_all(self, repo):
        assert repo.list_by_month("2026-07") == []
        assert repo.total_in("2026-07") == Decimal(0)
        assert repo.total_out("2026-07") == Decimal(0)
        assert repo.cashflow("2026-07") == Decimal(0)

    def test_month_with_transactions_but_none_of_the_requested_flow_type(
        self, repo, make_transaction
    ):
        make_transaction(
            day=date(2026, 3, 1), amount="10", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_by_flow(FlowType.EPARGNE, "2026-03") == Decimal(0)

    def test_month_with_transactions_but_none_for_the_requested_category(
        self, repo, make_transaction
    ):
        make_transaction(
            day=date(2026, 3, 1), amount="10", sense=SenseType.SORTIE, flow_type=FlowType.DEPENSE
        )

        assert repo.total_spent_by_category(uuid.uuid4(), "2026-03") == Decimal(0)
