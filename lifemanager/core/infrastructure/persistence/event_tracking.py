"""Shared event tracking behavior for repositories."""

from __future__ import annotations

from lifemanager.core.ports.event_publisher import DomainEvent, EventSource


class EventTrackingRepository:
    """Track domain entities for Unit of Work event collection."""

    def __init__(self) -> None:
        self._tracked_entities: list[EventSource] = []

    def _track(self, entity: EventSource) -> None:
        """Track an entity once for the lifetime of this repository."""
        if not any(tracked is entity for tracked in self._tracked_entities):
            self._tracked_entities.append(entity)

    def collect_new_events(self) -> list[DomainEvent]:
        """Pull pending events from every tracked entity."""
        events: list[DomainEvent] = []
        for entity in self._tracked_entities:
            events.extend(entity.pull_events())
        return events
