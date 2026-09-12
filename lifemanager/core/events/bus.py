"""
Lightweight in-process event bus.

Decouples modules: Finance emits TransactionCreated,
Dashboard subscribes without knowing Finance exists.

Usage:
    # Publisher
    bus.emit("transaction.created", transaction)

    # Subscriber (at startup)
    bus.on("transaction.created", dashboard_ctrl.refresh)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def on(self, event: str, handler: Callable[..., None]) -> None:
        """Register a handler for an event."""
        self._listeners[event].append(handler)

    def off(self, event: str, handler: Callable[..., None]) -> None:
        """Unregister a handler."""
        self._listeners[event] = [
            h for h in self._listeners[event] if h is not handler
        ]

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event — all registered handlers are called synchronously."""
        for handler in self._listeners.get(event, []):
            handler(*args, **kwargs)


# Application-level singleton
bus = EventBus()

# ── Event name constants ───────────────────────────────────────────────────────
class Events:
    # Finance
    TRANSACTION_CREATED  = "transaction.created"
    TRANSACTION_DELETED  = "transaction.deleted"
    BUDGET_EXCEEDED      = "budget.exceeded"
    DEBT_UPDATED         = "debt.updated"
    GOAL_UPDATED         = "goal.updated"

    # Grocery
    LIST_VALIDATED       = "grocery.list.validated"
    LIST_IMPORTED        = "grocery.list.imported"

    # Nutrition
    PRODUCT_SYNCED       = "nutrition.product.synced"

    # App lifecycle
    APP_READY            = "app.ready"
    SETTINGS_CHANGED     = "settings.changed"
