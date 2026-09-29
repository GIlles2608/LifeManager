"""SQLAlchemy Unit of Work adapter for Finance."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Self, cast

from sqlalchemy.orm import Session

from lifemanager.finance.application.ports import AbstractUnitOfWork
from lifemanager.finance.domain.ports import DebtRepositoryPort
from lifemanager.finance.infrastructure.persistence.repositories import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    DebtRepository,
    SavingsGoalRepository,
    TransactionRepository,
)

SessionContextFactory = Callable[[], AbstractContextManager[Session]]


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """Bind Finance repositories to one SQLAlchemy session.

    The session is opened on ``__enter__`` and closed on ``__exit__``, so the
    unit of work owns its lifetime: one instance covers exactly one
    application operation and must not be reused afterwards.
    """

    def __init__(self, session_context_factory: SessionContextFactory) -> None:
        self._session_context_factory = session_context_factory
        self._session_context: AbstractContextManager[Session] | None = None
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session_context = self._session_context_factory()
        session = self._session_context.__enter__()
        self._session = session
        self.tx_repo = TransactionRepository(session)
        self.budget_repo = BudgetRepository(session)
        self.category_repo = CategoryRepository(session)
        self.debt_repo = cast(DebtRepositoryPort, DebtRepository(session))
        self.account_repo = AccountRepository(session)
        self.goal_repo = SavingsGoalRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session_context = self._session_context
        try:
            super().__exit__(exc_type, exc_value, traceback)
        finally:
            self._session = None
            self._session_context = None
            if session_context is not None:
                # get_session() commits on a clean exit and rolls back on an
                # exception; commit/rollback above already settled the
                # outcome, so the context only has to release the session.
                session_context.__exit__(exc_type, exc_value, traceback)

    def commit(self) -> None:
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
