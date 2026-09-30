"""Port for publishing domain events."""

from __future__ import annotations

from typing import ClassVar, Protocol


class DomainEvent:
    """Base contract implemented by every domain event."""

    event_name: ClassVar[str]


class EventSource(Protocol):
    """Entity capable of returning and clearing pending domain events."""

    def pull_events(self) -> list[DomainEvent]: ...


class EventCollectingRepository(Protocol):
    """Repository that tracks entities for Unit of Work event collection."""

    def collect_new_events(self) -> list[DomainEvent]: ...


class AbstractEventPublisher(Protocol):
    """Outbound channel used by a Unit of Work after a successful commit."""

    def publish(self, event: DomainEvent) -> None: ...
