"""Composition root for Finance infrastructure adapters."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from lifemanager.core.config.database import get_session
from lifemanager.finance.application.ports import AbstractUnitOfWork
from lifemanager.finance.application.services.finance_service import FinanceService
from lifemanager.finance.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

SessionContextFactory = Callable[[], AbstractContextManager[Session]]


def build_finance_service(
    session_context_factory: SessionContextFactory = get_session,
) -> FinanceService:
    """Compose the Finance service over SQLAlchemy persistence adapters.

    The service receives a factory rather than a session: it opens one unit of
    work — and therefore one session — per operation, instead of sharing a
    single long-lived session across the whole application run.
    """

    def build_unit_of_work() -> AbstractUnitOfWork:
        return SqlAlchemyUnitOfWork(session_context_factory)

    return FinanceService(build_unit_of_work)
