"""In-process event publisher adapter."""

from __future__ import annotations

from lifemanager.core.events.bus import bus
from lifemanager.core.ports.event_publisher import DomainEvent


class InProcessEventPublisher:
    """Adapt typed domain events to the existing in-process event bus."""

    def publish(self, event: DomainEvent) -> None:
        """Publish the typed event using its stable routing name."""
        bus.emit(event.event_name, event)
