"""
Unit tests for FinanceController — no DB, no real service.

We patch the symbols at controller-module level so:
- get_session() returns a context-manager yielding a MagicMock session
- FinanceService(...) returns a MagicMock service we can drive per-test

Qt signals are exercised via pytest-qt's qtbot.waitSignal / capture pattern.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lifemanager.core.exceptions.exceptions import NotFoundError, ValidationError
from lifemanager.finance.application.dto import TransactionDTO
from lifemanager.finance.controllers.finance_controller import FinanceController
from lifemanager.finance.models import FlowType, SenseType
from lifemanager.finance.services.finance_service import (
    BudgetCheckResult,
    MonthlyKPIs,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_service():
    """A MagicMock standing in for FinanceService."""
    return MagicMock()


@pytest.fixture
def controller(qtbot, mock_service):
    """
    FinanceController wired so that:
    - get_session() yields a dummy session (we don't care which one)
    - FinanceService(session) returns our pre-configured mock_service
    """
    @contextmanager
    def fake_get_session():
        yield MagicMock(name="session")

    with patch(
        "lifemanager.finance.controllers.finance_controller.get_session",
        fake_get_session,
    ), patch(
        "lifemanager.finance.bootstrap.build_finance_service",
        return_value=mock_service,
    ):
        ctl = FinanceController()
        qtbot.addWidget  # noqa: B018  - sanity that qtbot is alive (no widget here)
        yield ctl


def _valid_dto() -> TransactionDTO:
    return TransactionDTO(
        date=date(2026, 5, 1),
        amount=Decimal("50.00"),
        flow_type=FlowType.DEPENSE,
        sense=SenseType.SORTIE,
        label="Courses",
        account_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
    )


def _capture(signal: Any) -> list[tuple[Any, ...]]:
    """Connect a list-collector to a Qt signal; return the list."""
    captured: list[tuple[Any, ...]] = []
    signal.connect(lambda *args: captured.append(args))
    return captured


# ── create_transaction ────────────────────────────────────────────────────────


class TestCreateTransaction:
    def test_returns_tx_and_emits_on_success(self, controller, mock_service):
        fake_tx = MagicMock(name="Transaction")
        mock_service.create_transaction.return_value = fake_tx
        captured = _capture(controller.transaction_created)

        result = controller.create_transaction(_valid_dto())

        assert result is fake_tx
        assert captured == [(fake_tx,)]

    def test_returns_none_and_emits_error_on_validation(
        self, controller, mock_service
    ):
        mock_service.create_transaction.side_effect = ValidationError("amount must be positive")
        ok_capt = _capture(controller.transaction_created)
        err_capt = _capture(controller.error)

        result = controller.create_transaction(_valid_dto())

        assert result is None
        assert ok_capt == []
        assert err_capt == [("amount must be positive",)]

    def test_unexpected_exception_propagates(self, controller, mock_service):
        """Non-domain exceptions must crash loud — they signal real bugs."""
        mock_service.create_transaction.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            controller.create_transaction(_valid_dto())


# ── delete_transaction ────────────────────────────────────────────────────────


class TestDeleteTransaction:
    def test_success_returns_true_and_emits(self, controller, mock_service):
        tx_id = uuid.uuid4()
        captured = _capture(controller.transaction_deleted)

        ok = controller.delete_transaction(tx_id)

        assert ok is True
        mock_service.delete_transaction.assert_called_once_with(tx_id)
        assert captured == [(tx_id,)]

    def test_not_found_returns_false_and_emits_error(self, controller, mock_service):
        mock_service.delete_transaction.side_effect = NotFoundError("Transaction", "x")
        del_capt = _capture(controller.transaction_deleted)
        err_capt = _capture(controller.error)

        ok = controller.delete_transaction(uuid.uuid4())

        assert ok is False
        assert del_capt == []
        assert len(err_capt) == 1


# ── get_monthly_kpis ──────────────────────────────────────────────────────────


class TestGetMonthlyKPIs:
    def test_returns_kpis_and_emits(self, controller, mock_service):
        kpis = MonthlyKPIs(
            month="2026-05",
            revenues=Decimal("1200"),
            expenses=Decimal("600"),
            savings=Decimal("80"),
            debt_repayments=Decimal("100"),
            net=Decimal("420"),
        )
        mock_service.get_monthly_kpis.return_value = kpis
        captured = _capture(controller.kpis_refreshed)

        result = controller.get_monthly_kpis("2026-05")

        assert result is kpis
        assert captured == [(kpis,)]


# ── check_budget ──────────────────────────────────────────────────────────────


class TestCheckBudget:
    def test_returns_result_and_emits(self, controller, mock_service):
        result = BudgetCheckResult(
            category_name="Alim",
            ceiling=Decimal("200"),
            spent=Decimal("250"),
            remaining=Decimal("0"),
            is_exceeded=True,
        )
        mock_service.check_budget.return_value = result
        captured = _capture(controller.budget_checked)

        out = controller.check_budget(uuid.uuid4(), "2026-05")

        assert out is result
        assert captured == [(result,)]


# ── update_debt_balance ───────────────────────────────────────────────────────


class TestUpdateDebtBalance:
    def test_success_returns_true_and_emits(self, controller, mock_service):
        captured = _capture(controller.debt_updated)
        ok = controller.update_debt_balance(uuid.uuid4(), Decimal("500"))

        assert ok is True
        assert len(captured) == 1

    def test_negative_balance_returns_false_and_emits_error(
        self, controller, mock_service
    ):
        mock_service.update_debt_balance.side_effect = ValidationError("negative")
        debt_capt = _capture(controller.debt_updated)
        err_capt = _capture(controller.error)

        ok = controller.update_debt_balance(uuid.uuid4(), Decimal("-1"))

        assert ok is False
        assert debt_capt == []
        assert err_capt == [("negative",)]
