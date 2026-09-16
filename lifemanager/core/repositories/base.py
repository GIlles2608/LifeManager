"""
Generic base repository — provides CRUD primitives shared by every repo.

Subclasses set the ``model`` class attribute and add domain-specific queries.
"""

from __future__ import annotations

import uuid
from typing import ClassVar, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from lifemanager.core.exceptions.exceptions import NotFoundError
from lifemanager.core.models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """CRUD primitives. Subclasses must set ``model``."""

    model: ClassVar[type[BaseModel]]

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Write ──────────────────────────────────────────────────────────────────

    def add(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity

    def delete(self, entity_id: uuid.UUID) -> None:
        entity = self.get_by_id(entity_id)
        self._session.delete(entity)
        self._session.flush()

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_by_id(self, entity_id: uuid.UUID) -> T:
        entity = self._session.get(self.model, entity_id)
        if entity is None:
            raise NotFoundError(self.model.__name__, entity_id)
        return entity  # type: ignore[return-value]

    def find_by_id(self, entity_id: uuid.UUID) -> T | None:
        """Like get_by_id, but returns None instead of raising."""
        return self._session.get(self.model, entity_id)  # type: ignore[return-value]

    def list_all(self) -> list[T]:
        stmt = select(self.model)
        return list(self._session.scalars(stmt))
