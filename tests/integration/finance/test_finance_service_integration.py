"""Integration tests for FinanceService over real persistence (ADR-0006).

The unit tests drive the service through a FakeUnitOfWork; these drive it
through `build_finance_service`, so the assertions cover what the fake cannot:
that one service call maps to one committed PostgreSQL transaction, and that a
failing call leaves no trace behind.

Like the unit-of-work tests, they need real commits and therefore use the
`truncate_tables` fallback rather than the rollback-based `db_session`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from lifemanager.core.events.bus import Events, bus
from lifemanager.core.exceptions.exceptions import NotFoundError
from lifemanager.finance.application.dto import TransactionDTO
from lifemanager.finance.application.services.finance_service import FinanceService
from lifemanager.finance.domain.enums import (
    AccountType,
    DebtStatus,
    FlowType,
    GrandType,
    SenseType,
)
from lifemanager.finance.domain.exceptions import ValidationError
from lifemanager.finance.infrastructure.bootstrap import build_finance_service
from lifemanager.finance.models import Account, Budget, Category, Debt, Transaction

SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@pytest.fixture
def session_factory(db_engine: Engine) -> SessionContextFactory:
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)

    @contextmanager
    def _session_context() -> Iterator[Session]:
        # Same contract as core.config.database.get_session(): commit on a
        # clean exit, roll back on exception. Anything the unit of work fails
        # to roll back would therefore be committed here - which is what lets
        # these tests detect a broken rollback.
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _session_context


@pytest.fixture
def service(session_factory: SessionContextFactory, truncate_tables: None) -> FinanceService:
    """The real service, composed exactly as the application composes it."""
    return build_finance_service(session_factory)


@pytest.fixture
def account_id(db_engine: Engine) -> uuid.UUID:
    entity_id = uuid.uuid4()
    with sessionmaker(bind=db_engine)() as session:
        session.add(
            Account(
                id=entity_id,
                name="Compte courant",
                type=AccountType.COURANT.value,
                initial_balance=Decimal(0),
            )
        )
        session.commit()
    return entity_id


@pytest.fixture
def category_id(db_engine: Engine) -> uuid.UUID:
    entity_id = uuid.uuid4()
    with sessionmaker(bind=db_engine)() as session:
        session.add(
            Category(
                id=entity_id,
                name="Alimentation",
                grand_type=GrandType.DEPENSE.value,
            )
        )
        session.commit()
    return entity_id


def _dto(account_id: uuid.UUID, **overrides: object) -> TransactionDTO:
    base = {
        "date": date(2026, 3, 15),
        "amount": Decimal("50.00"),
        "flow_type": FlowType.DEPENSE,
        "sense": SenseType.SORTIE,
        "label": "Courses",
        "account_id": account_id,
        "category_id": None,
    }
    base.update(overrides)
    return TransactionDTO(**base)  # type: ignore[arg-type]


def _count_transactions(db_engine: Engine) -> int:
    with sessionmaker(bind=db_engine)() as session:
        return len(list(session.scalars(select(Transaction))))


class TestCreateTransaction:
    def test_persists_the_transaction(
        self, service: FinanceService, db_engine: Engine, account_id: uuid.UUID
    ) -> None:
        result = service.create_transaction(_dto(account_id))

        assert result.label == "Courses"
        assert _count_transactions(db_engine) == 1

    def test_returns_a_read_dto_carrying_the_account_name(
        self, service: FinanceService, account_id: uuid.UUID
    ) -> None:
        result = service.create_transaction(_dto(account_id))

        assert result.account_name == "Compte courant"

    def test_invalid_dto_persists_nothing(
        self, service: FinanceService, db_engine: Engine, account_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            service.create_transaction(_dto(account_id, amount=Decimal(-5)))

        assert _count_transactions(db_engine) == 0

    def test_unknown_account_rolls_the_whole_operation_back(
        self, service: FinanceService, db_engine: Engine
    ) -> None:
        # The foreign key fails at flush: nothing may remain committed.
        with pytest.raises(IntegrityError):
            service.create_transaction(_dto(uuid.uuid4()))

        assert _count_transactions(db_engine) == 0


class TestBudgetInteraction:
    def test_exceeding_the_ceiling_emits_budget_exceeded(
        self,
        service: FinanceService,
        db_engine: Engine,
        account_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        with sessionmaker(bind=db_engine)() as session:
            session.add(
                Budget(
                    id=uuid.uuid4(),
                    month="2026-03",
                    ceiling=Decimal(30),
                    category_id=category_id,
                )
            )
            session.commit()

        captured: list[object] = []
        bus.on(Events.BUDGET_EXCEEDED, captured.append)
        try:
            service.create_transaction(_dto(account_id, category_id=category_id))
        finally:
            bus.off(Events.BUDGET_EXCEEDED, captured.append)

        assert len(captured) == 1

    def test_budget_check_sees_the_transaction_being_created(
        self,
        service: FinanceService,
        db_engine: Engine,
        account_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> None:
        # 50 spent against a ceiling of 40: the check only exceeds if it runs
        # inside the same transaction as the insert it is checking.
        with sessionmaker(bind=db_engine)() as session:
            session.add(
                Budget(
                    id=uuid.uuid4(),
                    month="2026-03",
                    ceiling=Decimal(40),
                    category_id=category_id,
                )
            )
            session.commit()

        service.create_transaction(_dto(account_id, category_id=category_id))

        result = service.check_budget(category_id, "2026-03")
        assert result.spent == Decimal("50.00")
        assert result.is_exceeded is True


class TestReadOperations:
    def test_list_transactions_returns_committed_rows(
        self, service: FinanceService, account_id: uuid.UUID
    ) -> None:
        service.create_transaction(_dto(account_id))

        rows = service.list_transactions("2026-03")

        assert len(rows) == 1
        assert rows[0].label == "Courses"

    def test_monthly_kpis_aggregate_committed_transactions(
        self, service: FinanceService, account_id: uuid.UUID
    ) -> None:
        service.create_transaction(
            _dto(
                account_id,
                amount=Decimal(1200),
                flow_type=FlowType.REVENU,
                sense=SenseType.ENTREE,
                label="Salaire",
            )
        )
        service.create_transaction(_dto(account_id, amount=Decimal(200)))

        kpis = service.get_monthly_kpis("2026-03")

        assert kpis.revenues == Decimal(1200)
        assert kpis.expenses == Decimal(200)
        assert kpis.net == Decimal(1000)

    def test_list_accounts_returns_the_seeded_account(
        self, service: FinanceService, account_id: uuid.UUID
    ) -> None:
        accounts = service.list_accounts()

        assert [a.id for a in accounts] == [account_id]


class TestUpdateDebtBalance:
    @pytest.fixture
    def debt_id(self, db_engine: Engine) -> uuid.UUID:
        entity_id = uuid.uuid4()
        with sessionmaker(bind=db_engine)() as session:
            session.add(
                Debt(
                    id=entity_id,
                    name="Pret auto",
                    debt_type="pret",
                    initial_amount=Decimal(1000),
                    current_balance=Decimal(1000),
                    monthly_target=Decimal(100),
                    status=DebtStatus.ACTIVE.value,
                    started_at=date(2026, 1, 1),
                )
            )
            session.commit()
        return entity_id

    def test_new_balance_is_committed(
        self, service: FinanceService, db_engine: Engine, debt_id: uuid.UUID
    ) -> None:
        service.update_debt_balance(debt_id, Decimal(500))

        with sessionmaker(bind=db_engine)() as session:
            stored = session.get(Debt, debt_id)
            assert stored is not None
            assert stored.current_balance == Decimal(500)

    def test_unknown_debt_raises_and_changes_nothing(
        self, service: FinanceService, db_engine: Engine, debt_id: uuid.UUID
    ) -> None:
        with pytest.raises(NotFoundError):
            service.update_debt_balance(uuid.uuid4(), Decimal(500))

        with sessionmaker(bind=db_engine)() as session:
            stored = session.get(Debt, debt_id)
            assert stored is not None
            assert stored.current_balance == Decimal(1000)

    def test_negative_balance_is_rejected_before_touching_the_database(
        self, service: FinanceService, db_engine: Engine, debt_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            service.update_debt_balance(debt_id, Decimal(-1))

        with sessionmaker(bind=db_engine)() as session:
            stored = session.get(Debt, debt_id)
            assert stored is not None
            assert stored.current_balance == Decimal(1000)


class TestDeleteTransaction:
    def test_removes_the_committed_row(
        self, service: FinanceService, db_engine: Engine, account_id: uuid.UUID
    ) -> None:
        created = service.create_transaction(_dto(account_id))

        service.delete_transaction(created.id)

        assert _count_transactions(db_engine) == 0

    def test_deleting_an_unknown_id_leaves_existing_rows_untouched(
        self, service: FinanceService, db_engine: Engine, account_id: uuid.UUID
    ) -> None:
        service.create_transaction(_dto(account_id))

        with pytest.raises(NotFoundError):
            service.delete_transaction(uuid.uuid4())

        assert _count_transactions(db_engine) == 1
