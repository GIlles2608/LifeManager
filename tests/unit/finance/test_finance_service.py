"""Unit tests for FinanceService — no DB required (mocked session)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from lifemanager.core.events.bus import Events, bus
from lifemanager.core.exceptions.exceptions import NotFoundError, ValidationError
from lifemanager.finance.application.dto import TransactionDTO
from lifemanager.finance.models import FlowType, SenseType, Transaction
from lifemanager.finance.services.finance_service import (
    BudgetCheckResult,
    FinanceService,
    MonthlyKPIs,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def service(mock_session):
    tx = MagicMock()
    budget = MagicMock()
    category = MagicMock()
    debt = MagicMock()
    account = MagicMock()
    goal = MagicMock()
    svc = FinanceService(
        tx_repo=tx,
        budget_repo=budget,
        category_repo=category,
        debt_repo=debt,
        account_repo=account,
        goal_repo=goal,
    )
    return svc


@pytest.fixture
def captured_events():
    """Capture every event emitted on the global bus during a test."""
    captured: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def make_listener(event_name: str):
        def listener(*args, **kwargs):
            captured.append((event_name, args, kwargs))

        return listener

    listeners = {}
    for event in (
        Events.TRANSACTION_CREATED,
        Events.TRANSACTION_DELETED,
        Events.BUDGET_EXCEEDED,
        Events.DEBT_UPDATED,
    ):
        h = make_listener(event)
        listeners[event] = h
        bus.on(event, h)

    yield captured

    for event, h in listeners.items():
        bus.off(event, h)


def _valid_dto(**overrides: Any) -> TransactionDTO:
    base = TransactionDTO(
        date=date(2026, 5, 1),
        amount=Decimal("50.00"),
        flow_type=FlowType.DEPENSE,
        sense=SenseType.SORTIE,
        label="Courses",
        account_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
    )
    return replace(base, **overrides)


# ── Validation ────────────────────────────────────────────────────────────────


class TestTransactionValidation:
    def test_negative_amount_raises(self, service):
        with pytest.raises(ValidationError, match="positive"):
            service._validate_transaction(_valid_dto(amount=Decimal(-10)))

    def test_zero_amount_raises(self, service):
        with pytest.raises(ValidationError, match="positive"):
            service._validate_transaction(_valid_dto(amount=Decimal(0)))

    def test_blank_label_raises(self, service):
        with pytest.raises(ValidationError, match="label"):
            service._validate_transaction(_valid_dto(label="   "))

    def test_dette_without_debt_id_raises(self, service):
        dto = _valid_dto(
            flow_type=FlowType.DETTE,
            category_id=None,
            debt_id=None,
        )
        with pytest.raises(ValidationError, match="Debt"):
            service._validate_transaction(dto)

    def test_epargne_without_goal_id_raises(self, service):
        dto = _valid_dto(
            flow_type=FlowType.EPARGNE,
            category_id=None,
            goal_id=None,
        )
        with pytest.raises(ValidationError, match="SavingsGoal"):
            service._validate_transaction(dto)

    def test_debt_id_on_non_dette_raises(self, service):
        dto = _valid_dto(debt_id=uuid.uuid4())  # flow_type=DEPENSE by default
        with pytest.raises(ValidationError, match="Only DETTE"):
            service._validate_transaction(dto)

    def test_goal_id_on_non_epargne_raises(self, service):
        dto = _valid_dto(goal_id=uuid.uuid4())
        with pytest.raises(ValidationError, match="Only EPARGNE"):
            service._validate_transaction(dto)

    def test_valid_depense_passes(self, service):
        service._validate_transaction(_valid_dto())  # should not raise

    def test_valid_dette_passes(self, service):
        dto = _valid_dto(
            flow_type=FlowType.DETTE,
            category_id=None,
            debt_id=uuid.uuid4(),
        )
        service._validate_transaction(dto)


# ── create_transaction ────────────────────────────────────────────────────────


class TestCreateTransaction:
    def test_persists_via_repo_and_emits_event(self, service, captured_events):
        service._tx_repo.add.side_effect = lambda tx: tx  # passthrough

        dto = _valid_dto(category_id=None)  # no category -> skip budget check
        service.create_transaction(dto)

        service._tx_repo.add.assert_called_once()
        persisted = service._tx_repo.add.call_args.args[0]
        assert isinstance(persisted, Transaction)
        assert persisted.amount == dto.amount
        service._tx_repo.read_by_id.assert_called_once_with(persisted.id)
        events = [e[0] for e in captured_events]
        assert Events.TRANSACTION_CREATED in events
        assert Events.BUDGET_EXCEEDED not in events

    def test_emits_budget_exceeded_when_over_ceiling(self, service, captured_events):
        service._tx_repo.add.side_effect = lambda tx: tx
        # Budget exists, ceiling=100, spent=150 => exceeded
        budget = MagicMock(ceiling=Decimal(100))
        category = MagicMock(name="cat-mock")
        category.name = "Alimentation"
        service._budget_repo.get_by_category_and_month.return_value = budget
        service._category_repo.find_read_by_id.return_value = category
        service._tx_repo.total_spent_by_category.return_value = Decimal(150)

        service.create_transaction(_valid_dto())

        budget_events = [e for e in captured_events if e[0] == Events.BUDGET_EXCEEDED]
        assert len(budget_events) == 1
        result = budget_events[0][1][0]
        assert isinstance(result, BudgetCheckResult)
        assert result.is_exceeded
        assert result.category_name == "Alimentation"

    def test_no_budget_check_when_no_category(self, service, captured_events):
        service._tx_repo.add.side_effect = lambda tx: tx
        service.create_transaction(_valid_dto(category_id=None))

        service._budget_repo.get_by_category_and_month.assert_not_called()
        assert Events.BUDGET_EXCEEDED not in [e[0] for e in captured_events]

    def test_no_budget_check_for_non_depense(self, service, captured_events):
        service._tx_repo.add.side_effect = lambda tx: tx
        dto = _valid_dto(
            flow_type=FlowType.REVENU,
            sense=SenseType.ENTREE,
            category_id=uuid.uuid4(),
        )
        service.create_transaction(dto)

        service._budget_repo.get_by_category_and_month.assert_not_called()


# ── delete_transaction ────────────────────────────────────────────────────────


class TestDeleteTransaction:
    def test_delegates_to_repo_and_emits(self, service, captured_events):
        tx_id = uuid.uuid4()
        service.delete_transaction(tx_id)

        service._tx_repo.delete.assert_called_once_with(tx_id)
        deleted = [e for e in captured_events if e[0] == Events.TRANSACTION_DELETED]
        assert len(deleted) == 1
        assert deleted[0][1][0] == tx_id


# ── check_budget ──────────────────────────────────────────────────────────────


class TestCheckBudget:
    def test_no_budget_means_not_exceeded(self, service):
        service._budget_repo.get_by_category_and_month.return_value = None
        category = MagicMock()
        category.name = "Loisirs"
        service._category_repo.find_by_id.return_value = category
        service._tx_repo.total_spent_by_category.return_value = Decimal(999)

        result = service.check_budget(uuid.uuid4(), "2026-05")

        assert result.ceiling == Decimal(0)
        assert result.spent == Decimal(999)
        assert result.is_exceeded is False  # no ceiling defined
        assert result.remaining == Decimal(0)

    def test_within_budget(self, service):
        service._budget_repo.get_by_category_and_month.return_value = MagicMock(
            ceiling=Decimal(200)
        )
        cat = MagicMock()
        cat.name = "Alim"
        service._category_repo.find_by_id.return_value = cat
        service._tx_repo.total_spent_by_category.return_value = Decimal(80)

        result = service.check_budget(uuid.uuid4(), "2026-05")

        assert result.is_exceeded is False
        assert result.remaining == Decimal(120)

    def test_exceeded(self, service):
        service._budget_repo.get_by_category_and_month.return_value = MagicMock(
            ceiling=Decimal(200)
        )
        cat = MagicMock()
        cat.name = "Alim"
        service._category_repo.find_by_id.return_value = cat
        service._tx_repo.total_spent_by_category.return_value = Decimal(250)

        result = service.check_budget(uuid.uuid4(), "2026-05")

        assert result.is_exceeded is True
        assert result.remaining == Decimal(0)  # clamped to 0


# ── get_monthly_kpis ──────────────────────────────────────────────────────────


class TestMonthlyKPIs:
    def test_returns_typed_dataclass(self, service):
        service._tx_repo.total_by_flow.return_value = Decimal(0)
        kpis = service.get_monthly_kpis("2026-05")
        assert isinstance(kpis, MonthlyKPIs)
        assert kpis.month == "2026-05"

    def test_net_calculation(self, service):
        # Revenues 1200, Expenses 600, Savings 80, Debts 100 => Net = 420
        returns = {
            FlowType.REVENU: Decimal(1200),
            FlowType.DEPENSE: Decimal(600),
            FlowType.EPARGNE: Decimal(80),
            FlowType.DETTE: Decimal(100),
        }
        service._tx_repo.total_by_flow.side_effect = lambda ft, m: returns[ft]

        kpis = service.get_monthly_kpis("2026-05")

        assert kpis.revenues == Decimal(1200)
        assert kpis.expenses == Decimal(600)
        assert kpis.savings == Decimal(80)
        assert kpis.debt_repayments == Decimal(100)
        assert kpis.net == Decimal(420)


# ── update_debt_balance ───────────────────────────────────────────────────────


class TestUpdateDebtBalance:
    def test_updates_and_emits(self, service, captured_events):
        debt = MagicMock()
        service._debt_repo.find_by_id.return_value = debt

        service.update_debt_balance(uuid.uuid4(), Decimal(500))

        assert debt.current_balance == Decimal(500)
        assert Events.DEBT_UPDATED in [e[0] for e in captured_events]

    def test_unknown_debt_raises(self, service):
        service._debt_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.update_debt_balance(uuid.uuid4(), Decimal(500))

    def test_negative_balance_raises(self, service):
        with pytest.raises(ValidationError, match="negative"):
            service.update_debt_balance(uuid.uuid4(), Decimal(-1))
