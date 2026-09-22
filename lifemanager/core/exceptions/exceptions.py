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


class ValidationError(LifeManagerError):
    """Deprecated compatibility error for callers using the old core path."""


# ── External services ─────────────────────────────────────────────────────────
class ExternalAPIError(LifeManagerError):
    """Raised when an external API call fails."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(f"[{service}] {detail}")
