"""Business exceptions owned by the Finance domain."""

from __future__ import annotations


class FinanceDomainError(Exception):
    """Base class for Finance business-rule failures."""


class ValidationError(FinanceDomainError):
    """Raised when Finance input violates a business rule."""


class BudgetExceededError(FinanceDomainError):
    """Raised when a transaction exceeds a budget ceiling."""

    def __init__(self, category: str, ceiling: float, actual: float) -> None:
        super().__init__(
            f"Budget exceeded for '{category}': ceiling={ceiling:.2f}€, actual={actual:.2f}€"
        )


class InsufficientFundsError(FinanceDomainError):
    """Raised when an account balance would become negative."""
