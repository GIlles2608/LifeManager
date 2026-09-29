"""Integration tests for SqlAlchemyUnitOfWork (ADR-0006).

These tests verify the transaction boundary itself against real PostgreSQL:
that leaving the `with` block commits, that an exception rolls back, and that
each unit of work owns its own session. They therefore cannot use the
`db_session` fixture, whose outer rollback would mask a real commit — they use
the `truncate_tables` fallback documented in ADR-0002 instead.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from lifemanager.finance.domain.entities import Transaction as TransactionEntity
from lifemanager.finance.domain.enums import AccountType, FlowType, GrandType, SenseType
from lifemanager.finance.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from lifemanager.finance.models import Account, Category, Transaction

SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@pytest.fixture
def session_factory(db_engine: Engine) -> SessionContextFactory:
    """A real committing session context, mirroring `get_session()`."""
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
def reference_data(db_engine: Engine, truncate_tables: None) -> tuple[uuid.UUID, uuid.UUID]:
    """Committed account and category, since each unit of work opens its own
    session and would not see uncommitted rows."""
    account_id = uuid.uuid4()
    category_id = uuid.uuid4()
    factory = sessionmaker(bind=db_engine)
    with factory() as session:
        session.add(
            Account(
                id=account_id,
                name="Compte courant",
                type=AccountType.COURANT.value,
                initial_balance=Decimal(0),
            )
        )
        session.add(
            Category(
                id=category_id,
                name="Alimentation",
                grand_type=GrandType.DEPENSE.value,
            )
        )
        session.commit()
    return account_id, category_id


def _transaction(account_id: uuid.UUID, amount: str = "42.00") -> TransactionEntity:
    return TransactionEntity(
        id=uuid.uuid4(),
        date=date(2026, 3, 15),
        amount=Decimal(amount),
        flow_type=FlowType.DEPENSE.value,
        sense=SenseType.SORTIE.value,
        label="Courses",
        account_id=account_id,
    )


def _stored_transaction_ids(db_engine: Engine) -> set[uuid.UUID]:
    with sessionmaker(bind=db_engine)() as session:
        return set(session.scalars(select(Transaction.id)))


class TestCommitOnCleanExit:
    def test_leaving_the_block_persists_the_write(
        self,
        db_engine: Engine,
        session_factory: SessionContextFactory,
        reference_data: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        account_id, _ = reference_data
        entity = _transaction(account_id)

        with SqlAlchemyUnitOfWork(session_factory) as uow:
            uow.tx_repo.add(entity)

        assert entity.id in _stored_transaction_ids(db_engine)

    def test_committed_row_is_visible_to_a_later_unit_of_work(
        self,
        session_factory: SessionContextFactory,
        reference_data: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        account_id, _ = reference_data
        entity = _transaction(account_id)

        with SqlAlchemyUnitOfWork(session_factory) as uow:
            uow.tx_repo.add(entity)

        with SqlAlchemyUnitOfWork(session_factory) as uow:
            assert uow.tx_repo.read_by_id(entity.id) is not None


class TestRollbackOnException:
    def test_an_exception_discards_the_write(
        self,
        db_engine: Engine,
        session_factory: SessionContextFactory,
        reference_data: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        account_id, _ = reference_data
        entity = _transaction(account_id)

        # Nested on purpose: pytest.raises must wrap the unit of work exit,
        # which is where the rollback happens.
        with pytest.raises(RuntimeError, match="boom"):  # noqa: SIM117
            with SqlAlchemyUnitOfWork(session_factory) as uow:
                uow.tx_repo.add(entity)
                raise RuntimeError("boom")

        assert entity.id not in _stored_transaction_ids(db_engine)

    def test_rollback_discards_every_write_of_the_operation(
        self,
        db_engine: Engine,
        session_factory: SessionContextFactory,
        reference_data: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        # Two writes, one failure: neither may survive — that is what makes
        # the unit of work a boundary rather than a per-statement commit.
        account_id, _ = reference_data
        first = _transaction(account_id, "10.00")
        second = _transaction(account_id, "20.00")

        with pytest.raises(RuntimeError), SqlAlchemyUnitOfWork(session_factory) as uow:
            uow.tx_repo.add(first)
            uow.tx_repo.add(second)
            raise RuntimeError("boom")

        stored = _stored_transaction_ids(db_engine)
        assert first.id not in stored
        assert second.id not in stored

    def test_rollback_does_not_rely_on_the_session_context(
        self,
        db_engine: Engine,
        reference_data: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        # The tests above pass the exception down to the session context,
        # whose own rollback would hide a broken one in the unit of work.
        # Here the context stays passive, so only SqlAlchemyUnitOfWork.rollback
        # can keep the write out of the database.
        account_id, _ = reference_data
        entity = _transaction(account_id)
        factory = sessionmaker(bind=db_engine, expire_on_commit=False)

        @contextmanager
        def passive_context() -> Iterator[Session]:
            session = factory()
            try:
                yield session
            finally:
                session.close()

        with pytest.raises(RuntimeError, match="boom"):  # noqa: SIM117
            with SqlAlchemyUnitOfWork(passive_context) as uow:
                uow.tx_repo.add(entity)
                raise RuntimeError("boom")

        assert entity.id not in _stored_transaction_ids(db_engine)

    def test_the_exception_still_propagates(
        self,
        session_factory: SessionContextFactory,
        reference_data: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        account_id, _ = reference_data

        with pytest.raises(ValueError, match="domain failure"):  # noqa: SIM117
            with SqlAlchemyUnitOfWork(session_factory) as uow:
                uow.tx_repo.add(_transaction(account_id))
                raise ValueError("domain failure")


class TestSessionLifecycle:
    def test_repositories_are_wired_on_entry(
        self, session_factory: SessionContextFactory
    ) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)

        with uow as entered:
            assert entered.tx_repo is not None
            assert entered.budget_repo is not None
            assert entered.category_repo is not None
            assert entered.debt_repo is not None
            assert entered.account_repo is not None
            assert entered.goal_repo is not None

    def test_session_is_released_after_exit(
        self, session_factory: SessionContextFactory
    ) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)
        with uow:
            pass

        assert uow._session is None

    def test_two_units_of_work_use_distinct_sessions(
        self, session_factory: SessionContextFactory
    ) -> None:
        with SqlAlchemyUnitOfWork(session_factory) as first:
            first_session = first._session
            with SqlAlchemyUnitOfWork(session_factory) as second:
                assert second._session is not first_session
