"""CategoryRepository — DB access for Category entities."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.models import Category, GrandType


class CategoryRepository(BaseRepository[Category]):
    model = Category

    def list_active(self) -> list[Category]:
        stmt = select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
        return list(self._session.scalars(stmt))

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
