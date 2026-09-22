"""Integration tests for DebtRepository."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from lifemanager.finance.models import Debt, DebtStatus
from lifemanager.finance.infrastructure.persistence.repositories.debt_repo import DebtRepository


@pytest.fixture
def repo(db_session) -> DebtRepository:
    return DebtRepository(db_session)


@pytest.fixture
def make_debt(db_session):
    """Factory for a Debt, one field per call."""

    def _make(
        *,
        name: str,
        status: DebtStatus = DebtStatus.ACTIVE,
        started_at: date,
        initial_amount: str = "1000",
        current_balance: str = "1000",
        monthly_target: str = "100",
        debt_type: str = "pret",
    ) -> Debt:
        debt = Debt(
            name=name,
            debt_type=debt_type,
            initial_amount=Decimal(initial_amount),
            current_balance=Decimal(current_balance),
            monthly_target=Decimal(monthly_target),
            status=status.value,
            started_at=started_at,
        )
        db_session.add(debt)
        db_session.flush()
        return debt

    return _make


class TestListActive:
    def test_excludes_non_active_statuses(self, repo, make_debt):
        active = make_debt(name="Prêt auto", status=DebtStatus.ACTIVE, started_at=date(2026, 1, 1))
        make_debt(name="Prêt soldé", status=DebtStatus.SOLDEE, started_at=date(2025, 1, 1))
        make_debt(name="Prêt suspendu", status=DebtStatus.SUSPENDUE, started_at=date(2024, 1, 1))

        result = repo.list_active()

        assert [d.id for d in result] == [active.id]

    def test_orders_by_started_at(self, repo, make_debt):
        later = make_debt(name="Récent", status=DebtStatus.ACTIVE, started_at=date(2026, 6, 1))
        earlier = make_debt(name="Ancien", status=DebtStatus.ACTIVE, started_at=date(2025, 1, 1))

        result = repo.list_active()

        assert [d.id for d in result] == [earlier.id, later.id]

    def test_no_active_debts_returns_empty_list(self, repo, make_debt):
        make_debt(name="Prêt soldé", status=DebtStatus.SOLDEE, started_at=date(2025, 1, 1))

        assert repo.list_active() == []
