"""Integration tests for BudgetRepository."""

from __future__ import annotations

from decimal import Decimal

import pytest

from lifemanager.finance.models import Budget, Category, GrandType
from lifemanager.finance.repositories.budget_repo import BudgetRepository


@pytest.fixture
def repo(db_session) -> BudgetRepository:
    return BudgetRepository(db_session)


@pytest.fixture
def make_budget(db_session):
    """Factory for a Budget tied to a given category and month."""

    def _make(*, category: Category, month: str, ceiling: str) -> Budget:
        budget = Budget(category_id=category.id, month=month, ceiling=Decimal(ceiling))
        db_session.add(budget)
        db_session.flush()
        return budget

    return _make


class TestGetByCategoryAndMonth:
    def test_returns_the_matching_budget(self, repo, make_budget, category):
        make_budget(category=category, month="2026-03", ceiling="200")

        result = repo.get_by_category_and_month(category.id, "2026-03")

        assert result is not None
        assert result.ceiling == Decimal(200)

    def test_returns_none_when_no_budget_exists(self, repo, category):
        assert repo.get_by_category_and_month(category.id, "2026-03") is None

    def test_does_not_match_a_different_month(self, repo, make_budget, category):
        make_budget(category=category, month="2026-03", ceiling="200")

        assert repo.get_by_category_and_month(category.id, "2026-04") is None

    def test_does_not_match_a_different_category(self, db_session, repo, make_budget, category):
        other_category = Category(name="Loisirs", grand_type=GrandType.DEPENSE)
        db_session.add(other_category)
        db_session.flush()
        make_budget(category=category, month="2026-03", ceiling="200")

        assert repo.get_by_category_and_month(other_category.id, "2026-03") is None


class TestListByMonth:
    def test_returns_all_budgets_for_the_month(self, db_session, repo, make_budget, category):
        other_category = Category(name="Loisirs", grand_type=GrandType.DEPENSE)
        db_session.add(other_category)
        db_session.flush()

        make_budget(category=category, month="2026-03", ceiling="200")
        make_budget(category=other_category, month="2026-03", ceiling="80")
        make_budget(category=category, month="2026-04", ceiling="150")

        result = repo.list_by_month("2026-03")

        assert {b.ceiling for b in result} == {Decimal(200), Decimal(80)}

    def test_month_with_no_budgets_returns_empty_list(self, repo):
        assert repo.list_by_month("2026-05") == []
