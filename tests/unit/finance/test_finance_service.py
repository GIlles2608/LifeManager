"""Unit tests for FinanceService — no DB, driven by an in-memory FakeUnitOfWork."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from lifemanager.core.events.bus import Events, bus
from lifemanager.core.exceptions.exceptions import NotFoundError
from lifemanager.finance.application.dto import (
    CategoryReadDTO,
    TransactionDTO,
    TransactionReadDTO,
)
from lifemanager.finance.application.services.finance_service import (
    BudgetCheckResult,
    FinanceService,
    MonthlyKPIs,
)
from lifemanager.finance.domain.entities import Budget, Debt
from lifemanager.finance.domain.enums import FlowType, SenseType
from lifemanager.finance.domain.exceptions import ValidationError
from tests.unit.finance.fakes import FakeUnitOfWork

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def uow() -> FakeUnitOfWork:
    """The unit of work the service under test will be handed."""
    return FakeUnitOfWork()


@pytest.fixture
def service(uow: FakeUnitOfWork) -> FinanceService:
    """Service wired to a factory returning the very same fake, so tests can
    inspect what the operation did after the method returns."""
    return FinanceService(lambda: uow)


@pytest.fixture
def captured_events() -> Iterator[list[tuple[str, tuple[Any, ...], dict[str, Any]]]]:
    """Capture every event emitted on the global bus during a test."""
    captured: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def make_listener(event_name: str) -> Any:
        def listener(*args: Any, **kwargs: Any) -> None:
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


def _read_row(tx_id: uuid.UUID) -> TransactionReadDTO:
    return TransactionReadDTO(
        id=tx_id,
        date=date(2026, 5, 1),
        amount=Decimal("50.00"),
        flow_type=FlowType.DEPENSE.value,
        sense=SenseType.SORTIE.value,
        label="Courses",
        account_id=uuid.uuid4(),
        account_name="Compte courant",
        category_id=None,
        category_name=None,
        debt_id=None,
        goal_id=None,
    )


def _category(category_id: uuid.UUID, name: str) -> CategoryReadDTO:
    return CategoryReadDTO(
        id=category_id,
        name=name,
        grand_type="depense",
        nature="variable",
        is_active=True,
        parent_id=None,
    )


def _answer_read_for_added(uow: FakeUnitOfWork) -> None:
    """Make read_by_id resolve any transaction added during the test."""
    original_add = uow.tx_repo.add

    def add_and_register(entity: Any) -> Any:
        result = original_add(entity)
        uow.tx_repo.read_rows[entity.id] = _read_row(entity.id)
        return result

    uow.tx_repo.add = add_and_register  # type: ignore[method-assign]


# ── Validation ────────────────────────────────────────────────────────────────


class TestTransactionValidation:
    def test_negative_amount_raises(self, service: FinanceService) -> None:
        with pytest.raises(ValidationError, match="positive"):
            service._validate_transaction(_valid_dto(amount=Decimal(-10)))

    def test_zero_amount_raises(self, service: FinanceService) -> None:
        with pytest.raises(ValidationError, match="positive"):
            service._validate_transaction(_valid_dto(amount=Decimal(0)))

    def test_blank_label_raises(self, service: FinanceService) -> None:
        with pytest.raises(ValidationError, match="label"):
            service._validate_transaction(_valid_dto(label="   "))

    def test_dette_without_debt_id_raises(self, service: FinanceService) -> None:
        dto = _valid_dto(flow_type=FlowType.DETTE, category_id=None, debt_id=None)
        with pytest.raises(ValidationError, match="Debt"):
            service._validate_transaction(dto)

    def test_epargne_without_goal_id_raises(self, service: FinanceService) -> None:
        dto = _valid_dto(flow_type=FlowType.EPARGNE, category_id=None, goal_id=None)
        with pytest.raises(ValidationError, match="SavingsGoal"):
            service._validate_transaction(dto)

    def test_debt_id_on_non_dette_raises(self, service: FinanceService) -> None:
        dto = _valid_dto(debt_id=uuid.uuid4())  # flow_type=DEPENSE by default
        with pytest.raises(ValidationError, match="Only DETTE"):
            service._validate_transaction(dto)

    def test_goal_id_on_non_epargne_raises(self, service: FinanceService) -> None:
        dto = _valid_dto(goal_id=uuid.uuid4())
        with pytest.raises(ValidationError, match="Only EPARGNE"):
            service._validate_transaction(dto)

    def test_valid_depense_passes(self, service: FinanceService) -> None:
        service._validate_transaction(_valid_dto())  # should not raise

    def test_valid_dette_passes(self, service: FinanceService) -> None:
        dto = _valid_dto(flow_type=FlowType.DETTE, category_id=None, debt_id=uuid.uuid4())
        service._validate_transaction(dto)


# ── create_transaction ────────────────────────────────────────────────────────


class TestCreateTransaction:
    def test_persists_and_emits_event(
        self,
        service: FinanceService,
        uow: FakeUnitOfWork,
        captured_events: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        _answer_read_for_added(uow)

        dto = _valid_dto(category_id=None)  # no category -> skip budget check
        service.create_transaction(dto)

        assert len(uow.tx_repo.transactions) == 1
        persisted = next(iter(uow.tx_repo.transactions.values()))
        assert persisted.amount == dto.amount
        assert persisted.label == dto.label
        events = [e[0] for e in captured_events]
        assert Events.TRANSACTION_CREATED in events
        assert Events.BUDGET_EXCEEDED not in events

    def test_commits_once(self, service: FinanceService, uow: FakeUnitOfWork) -> None:
        _answer_read_for_added(uow)

        service.create_transaction(_valid_dto(category_id=None))

        assert uow.commits == 1
        assert uow.rollbacks == 0

    def test_rolls_back_when_the_row_cannot_be_read_back(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        # read_by_id returns None: the service raises, so the unit of work
        # must roll back rather than commit a half-done operation.
        with pytest.raises(NotFoundError):
            service.create_transaction(_valid_dto(category_id=None))

        assert uow.rollbacks == 1
        assert uow.commits == 0

    def test_no_event_emitted_when_the_transaction_rolls_back(
        self,
        service: FinanceService,
        captured_events: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        with pytest.raises(NotFoundError):
            service.create_transaction(_valid_dto(category_id=None))

        assert captured_events == []

    def test_emits_budget_exceeded_when_over_ceiling(
        self,
        service: FinanceService,
        uow: FakeUnitOfWork,
        captured_events: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        _answer_read_for_added(uow)
        dto = _valid_dto()
        assert dto.category_id is not None
        # Budget exists, ceiling=100, spent=150 => exceeded
        uow.given_budget(
            Budget(
                id=uuid.uuid4(),
                month="2026-05",
                ceiling=Decimal(100),
                category_id=dto.category_id,
            ),
            "2026-05",
        )
        uow.given_category(_category(dto.category_id, "Alimentation"))
        uow.tx_repo.spent_by_category[(dto.category_id, "2026-05")] = Decimal(150)

        service.create_transaction(dto)

        budget_events = [e for e in captured_events if e[0] == Events.BUDGET_EXCEEDED]
        assert len(budget_events) == 1
        result = budget_events[0][1][0]
        assert isinstance(result, BudgetCheckResult)
        assert result.is_exceeded
        assert result.category_name == "Alimentation"

    def test_budget_check_shares_the_creating_transaction(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        # The nested budget check must run inside the same unit of work,
        # so the whole operation still commits exactly once.
        _answer_read_for_added(uow)
        dto = _valid_dto()
        assert dto.category_id is not None
        uow.given_category(_category(dto.category_id, "Alimentation"))

        service.create_transaction(dto)

        assert uow.entered == 1
        assert uow.commits == 1

    def test_no_budget_check_when_no_category(
        self,
        service: FinanceService,
        uow: FakeUnitOfWork,
        captured_events: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        _answer_read_for_added(uow)
        service.create_transaction(_valid_dto(category_id=None))

        assert uow.budget_repo.lookups == []
        assert Events.BUDGET_EXCEEDED not in [e[0] for e in captured_events]

    def test_no_budget_check_for_non_depense(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        _answer_read_for_added(uow)
        dto = _valid_dto(
            flow_type=FlowType.REVENU,
            sense=SenseType.ENTREE,
            category_id=uuid.uuid4(),
        )
        service.create_transaction(dto)

        assert uow.budget_repo.lookups == []


# ── delete_transaction ────────────────────────────────────────────────────────


class TestDeleteTransaction:
    def test_delegates_to_repo_and_emits(
        self,
        service: FinanceService,
        uow: FakeUnitOfWork,
        captured_events: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        tx_id = uuid.uuid4()
        service.delete_transaction(tx_id)

        assert uow.tx_repo.deleted == [tx_id]
        assert uow.commits == 1
        deleted = [e for e in captured_events if e[0] == Events.TRANSACTION_DELETED]
        assert len(deleted) == 1
        assert deleted[0][1][0] == tx_id


# ── check_budget ──────────────────────────────────────────────────────────────


class TestCheckBudget:
    def test_no_budget_means_not_exceeded(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        category_id = uuid.uuid4()
        uow.given_category(_category(category_id, "Loisirs"))
        uow.tx_repo.spent_by_category[(category_id, "2026-05")] = Decimal(999)

        result = service.check_budget(category_id, "2026-05")

        assert result.ceiling == Decimal(0)
        assert result.spent == Decimal(999)
        assert result.is_exceeded is False  # no ceiling defined
        assert result.remaining == Decimal(0)

    def test_within_budget(self, service: FinanceService, uow: FakeUnitOfWork) -> None:
        category_id = uuid.uuid4()
        uow.given_budget(
            Budget(
                id=uuid.uuid4(),
                month="2026-05",
                ceiling=Decimal(200),
                category_id=category_id,
            ),
            "2026-05",
        )
        uow.given_category(_category(category_id, "Alim"))
        uow.tx_repo.spent_by_category[(category_id, "2026-05")] = Decimal(80)

        result = service.check_budget(category_id, "2026-05")

        assert result.is_exceeded is False
        assert result.remaining == Decimal(120)

    def test_exceeded(self, service: FinanceService, uow: FakeUnitOfWork) -> None:
        category_id = uuid.uuid4()
        uow.given_budget(
            Budget(
                id=uuid.uuid4(),
                month="2026-05",
                ceiling=Decimal(200),
                category_id=category_id,
            ),
            "2026-05",
        )
        uow.given_category(_category(category_id, "Alim"))
        uow.tx_repo.spent_by_category[(category_id, "2026-05")] = Decimal(250)

        result = service.check_budget(category_id, "2026-05")

        assert result.is_exceeded is True
        assert result.remaining == Decimal(0)  # clamped to 0

    def test_unknown_category_falls_back_to_a_placeholder_name(
        self, service: FinanceService
    ) -> None:
        result = service.check_budget(uuid.uuid4(), "2026-05")

        assert result.category_name == "Inconnu"


# ── get_monthly_kpis ──────────────────────────────────────────────────────────


class TestMonthlyKPIs:
    def test_returns_typed_dataclass(self, service: FinanceService) -> None:
        kpis = service.get_monthly_kpis("2026-05")
        assert isinstance(kpis, MonthlyKPIs)
        assert kpis.month == "2026-05"

    def test_net_calculation(self, service: FinanceService, uow: FakeUnitOfWork) -> None:
        # Revenues 1200, Expenses 600, Savings 80, Debts 100 => Net = 420
        uow.tx_repo.totals_by_flow = {
            (FlowType.REVENU, "2026-05"): Decimal(1200),
            (FlowType.DEPENSE, "2026-05"): Decimal(600),
            (FlowType.EPARGNE, "2026-05"): Decimal(80),
            (FlowType.DETTE, "2026-05"): Decimal(100),
        }

        kpis = service.get_monthly_kpis("2026-05")

        assert kpis.revenues == Decimal(1200)
        assert kpis.expenses == Decimal(600)
        assert kpis.savings == Decimal(80)
        assert kpis.debt_repayments == Decimal(100)
        assert kpis.net == Decimal(420)


# ── update_debt_balance ───────────────────────────────────────────────────────


def _debt(debt_id: uuid.UUID) -> Debt:
    return Debt(
        id=debt_id,
        name="Pret",
        debt_type="personnel",
        initial_amount=Decimal(1000),
        current_balance=Decimal(1000),
        monthly_target=Decimal(100),
        status="active",
        started_at=date(2026, 1, 1),
    )


class TestUpdateDebtBalance:
    def test_updates_and_emits(
        self,
        service: FinanceService,
        uow: FakeUnitOfWork,
        captured_events: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        debt_id = uuid.uuid4()
        uow.given_debt(_debt(debt_id))

        service.update_debt_balance(debt_id, Decimal(500))

        assert len(uow.debt_repo.saved) == 1
        assert uow.debt_repo.saved[0].current_balance == Decimal(500)
        assert uow.commits == 1
        assert Events.DEBT_UPDATED in [e[0] for e in captured_events]

    def test_unknown_debt_raises(self, service: FinanceService) -> None:
        with pytest.raises(NotFoundError):
            service.update_debt_balance(uuid.uuid4(), Decimal(500))

    def test_unknown_debt_rolls_back(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        with pytest.raises(NotFoundError):
            service.update_debt_balance(uuid.uuid4(), Decimal(500))

        assert uow.rollbacks == 1
        assert uow.commits == 0

    def test_negative_balance_raises(self, service: FinanceService) -> None:
        with pytest.raises(ValidationError, match="negative"):
            service.update_debt_balance(uuid.uuid4(), Decimal(-1))

    def test_negative_balance_opens_no_transaction(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        # Validation happens before any unit of work is opened.
        with pytest.raises(ValidationError):
            service.update_debt_balance(uuid.uuid4(), Decimal(-1))

        assert uow.entered == 0


# ── read-only operations ──────────────────────────────────────────────────────


class TestReadOperations:
    def test_list_transactions_returns_rows_for_the_month(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        row = _read_row(uuid.uuid4())
        uow.tx_repo.rows_by_month["2026-05"] = [row]

        assert service.list_transactions("2026-05") == [row]

    def test_each_read_operation_opens_its_own_unit_of_work(
        self, service: FinanceService, uow: FakeUnitOfWork
    ) -> None:
        service.list_accounts()
        service.list_categories()
        service.list_active_debts()
        service.list_active_goals()

        assert uow.entered == 4
        assert uow.commits == 4
