"""Mappings between the SQLAlchemy Category model and domain entity."""

from __future__ import annotations

from lifemanager.finance.domain.entities import Category as CategoryEntity
from lifemanager.finance.models import Category


class CategoryMapper:
    """Convert category persistence rows to and from domain entities."""

    @staticmethod
    def to_entity(model: Category) -> CategoryEntity:
        return CategoryEntity(
            id=model.id,
            name=model.name,
            grand_type=model.grand_type,
            nature=model.nature,
            is_active=model.is_active,
            parent_id=model.parent_id,
        )

    @staticmethod
    def to_model(entity: CategoryEntity) -> Category:
        return Category(
            id=entity.id,
            name=entity.name,
            grand_type=entity.grand_type,
            nature=entity.nature,
            is_active=entity.is_active,
            parent_id=entity.parent_id,
        )
