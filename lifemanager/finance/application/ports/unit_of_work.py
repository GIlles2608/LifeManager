"""Application port for coordinating Finance repository transactions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import Self, TypeAlias

from lifemanager.core.ports.event_publisher import (
    AbstractEventPublisher,
    DomainEvent,
    EventCollectingRepository,
)
from lifemanager.finance.domain.ports import (
    AccountRepositoryPort,
    BudgetRepositoryPort,
    CategoryRepositoryPort,
    DebtRepositoryPort,
    SavingsGoalRepositoryPort,
    TransactionRepositoryPort,
)


class AbstractUnitOfWork(ABC):
    """Coordinate repository access and transaction boundaries."""

    tx_repo: TransactionRepositoryPort
    budget_repo: BudgetRepositoryPort
    category_repo: CategoryRepositoryPort
    debt_repo: DebtRepositoryPort
    account_repo: AccountRepositoryPort
    goal_repo: SavingsGoalRepositoryPort
    _event_repositories: tuple[EventCollectingRepository, ...] = ()
    _event_publisher: AbstractEventPublisher

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    def collect_new_events(self) -> list[DomainEvent]:
        """Drain events from repositories tracked by this unit of work."""
        events: list[DomainEvent] = []
        for repository in self._event_repositories:
            events.extend(repository.collect_new_events())
        return events

    @abstractmethod
    def commit(self) -> None:
        """Commit the current application transaction."""

    @abstractmethod
    def rollback(self) -> None:
        """Roll back the current application transaction."""


UnitOfWorkFactory: TypeAlias = Callable[[], AbstractUnitOfWork]
"""Builds a fresh Unit of Work per application operation.

The service owns no long-lived unit of work: it calls this factory once per
public method, so each operation gets its own transaction boundary.
"""
