"""CategoryRepository — DB access for Category entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.application.dto import CategoryReadDTO
from lifemanager.finance.models import Category, GrandType


class CategoryRepository(BaseRepository[Category]):
    model = Category

    def list_active(self) -> list[Category]:
        stmt = select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
        return list(self._session.scalars(stmt))

    def list_active_read(self) -> list[CategoryReadDTO]:
        """Return active categories without exposing ORM instances."""
        return [self._to_read_dto(category) for category in self.list_active()]

    def find_read_by_id(self, entity_id: uuid.UUID) -> CategoryReadDTO | None:
        """Return one category as a read DTO, if it exists."""
        category = self.find_by_id(entity_id)
        return self._to_read_dto(category) if category is not None else None

    @staticmethod
    def _to_read_dto(category: Category) -> CategoryReadDTO:
        return CategoryReadDTO(
            id=category.id,
            name=category.name,
            grand_type=category.grand_type,
            nature=category.nature,
            is_active=category.is_active,
            parent_id=category.parent_id,
        )

    def list_by_grand_type(self, grand_type: GrandType) -> list[Category]:
        stmt = (
            select(Category)
            .where(
                Category.grand_type == grand_type.value,
                Category.is_active.is_(True),
            )
            .order_by(Category.name)
        )
        return list(self._session.scalars(stmt))

    def list_children(self, parent_id: uuid.UUID) -> list[Category]:
        stmt = select(Category).where(Category.parent_id == parent_id).order_by(Category.name)
        return list(self._session.scalars(stmt))

    def list_roots(self) -> list[Category]:
        stmt = select(Category).where(Category.parent_id.is_(None)).order_by(Category.name)
        return list(self._session.scalars(stmt))
