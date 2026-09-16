"""Integration tests for CategoryRepository."""

from __future__ import annotations

import pytest

from lifemanager.finance.models import Category, GrandType
from lifemanager.finance.repositories.category_repo import CategoryRepository


@pytest.fixture
def repo(db_session) -> CategoryRepository:
    return CategoryRepository(db_session)


@pytest.fixture
def make_category(db_session):
    """Factory for a Category, one field per call."""

    def _make(
        *,
        name: str,
        grand_type: GrandType = GrandType.DEPENSE,
        is_active: bool = True,
        parent: Category | None = None,
    ) -> Category:
        cat = Category(
            name=name,
            grand_type=grand_type.value,
            is_active=is_active,
            parent_id=parent.id if parent else None,
        )
        db_session.add(cat)
        db_session.flush()
        return cat

    return _make


class TestListActive:
    def test_excludes_inactive_categories(self, repo, make_category):
        active = make_category(name="Alimentation", is_active=True)
        make_category(name="Obsolète", is_active=False)

        result = repo.list_active()

        assert [c.id for c in result] == [active.id]

    def test_orders_by_name(self, repo, make_category):
        make_category(name="Zorro")
        make_category(name="Alpha")

        names = [c.name for c in repo.list_active()]

        assert names == sorted(names)


class TestListByGrandType:
    def test_filters_by_grand_type(self, repo, make_category):
        make_category(name="Alimentation", grand_type=GrandType.DEPENSE)
        make_category(name="Salaire", grand_type=GrandType.REVENU)

        result = repo.list_by_grand_type(GrandType.DEPENSE)

        assert [c.name for c in result] == ["Alimentation"]

    def test_excludes_inactive_even_if_grand_type_matches(self, repo, make_category):
        make_category(name="Obsolète", grand_type=GrandType.DEPENSE, is_active=False)

        assert repo.list_by_grand_type(GrandType.DEPENSE) == []

    def test_grand_type_with_no_matches_returns_empty_list(self, repo, make_category):
        make_category(name="Alimentation", grand_type=GrandType.DEPENSE)

        assert repo.list_by_grand_type(GrandType.DETTE) == []


class TestListChildren:
    def test_returns_only_children_of_the_given_parent(self, repo, make_category):
        parent = make_category(name="Alimentation")
        other_parent = make_category(name="Loisirs")
        child = make_category(name="Restaurants", parent=parent)
        make_category(name="Cinéma", parent=other_parent)

        result = repo.list_children(parent.id)

        assert [c.id for c in result] == [child.id]

    def test_parent_with_no_children_returns_empty_list(self, repo, make_category):
        parent = make_category(name="Alimentation")

        assert repo.list_children(parent.id) == []


class TestListRoots:
    def test_returns_only_categories_without_a_parent(self, repo, make_category):
        root = make_category(name="Alimentation")
        make_category(name="Restaurants", parent=root)

        result = repo.list_roots()

        assert [c.id for c in result] == [root.id]
