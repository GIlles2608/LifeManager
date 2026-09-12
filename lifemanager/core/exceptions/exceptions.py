"""
Domain exception hierarchy.
All application errors derive from LifeManagerError.
"""


class LifeManagerError(Exception):
    """Root exception for all application errors."""


# ── Persistence ───────────────────────────────────────────────────────────────
class NotFoundError(LifeManagerError):
    """Raised when a requested entity does not exist."""
    def __init__(self, entity: str, id: object) -> None:
        super().__init__(f"{entity} with id={id} not found.")


class DuplicateError(LifeManagerError):
    """Raised on unique constraint violations."""


# ── Domain / Business ─────────────────────────────────────────────────────────
class ValidationError(LifeManagerError):
    """Raised when domain validation fails."""


class BudgetExceededError(LifeManagerError):
    """Raised when a transaction would exceed a budget ceiling."""
    def __init__(self, category: str, ceiling: float, actual: float) -> None:
        super().__init__(
            f"Budget exceeded for '{category}': ceiling={ceiling:.2f}€, actual={actual:.2f}€"
        )


class InsufficientFundsError(LifeManagerError):
    """Raised when account balance would go negative."""


# ── External services ─────────────────────────────────────────────────────────
class ExternalAPIError(LifeManagerError):
    """Raised when an external API call fails."""
    def __init__(self, service: str, detail: str) -> None:
        super().__init__(f"[{service}] {detail}")
