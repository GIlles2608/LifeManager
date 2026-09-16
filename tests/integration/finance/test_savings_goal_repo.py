"""Integration tests for SavingsGoalRepository."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from lifemanager.finance.models import GoalStatus, SavingsGoal
from lifemanager.finance.repositories.savings_goal_repo import SavingsGoalRepository


@pytest.fixture
def repo(db_session) -> SavingsGoalRepository:
    return SavingsGoalRepository(db_session)


@pytest.fixture
def make_goal(db_session):
    """Factory for a SavingsGoal, one field per call."""

    def _make(
        *,
        name: str,
        status: GoalStatus = GoalStatus.ACTIF,
        target_date: date,
        target_amount: str = "1000",
        current_amount: str = "0",
        monthly_target: str = "100",
    ) -> SavingsGoal:
        goal = SavingsGoal(
            name=name,
            target_amount=Decimal(target_amount),
            current_amount=Decimal(current_amount),
            monthly_target=Decimal(monthly_target),
            target_date=target_date,
            status=status.value,
        )
        db_session.add(goal)
        db_session.flush()
        return goal

    return _make


class TestListActive:
    def test_excludes_non_actif_statuses(self, repo, make_goal):
        active = make_goal(name="Vacances", status=GoalStatus.ACTIF, target_date=date(2026, 12, 1))
        make_goal(name="Voiture", status=GoalStatus.ATTEINT, target_date=date(2026, 1, 1))
        make_goal(name="Piscine", status=GoalStatus.ABANDONNE, target_date=date(2026, 6, 1))

        result = repo.list_active()

        assert [g.id for g in result] == [active.id]

    def test_orders_by_target_date(self, repo, make_goal):
        later = make_goal(name="Vacances", status=GoalStatus.ACTIF, target_date=date(2027, 1, 1))
        earlier = make_goal(name="Urgence", status=GoalStatus.ACTIF, target_date=date(2026, 3, 1))

        result = repo.list_active()

        assert [g.id for g in result] == [earlier.id, later.id]

    def test_no_active_goals_returns_empty_list(self, repo, make_goal):
        make_goal(name="Voiture", status=GoalStatus.ATTEINT, target_date=date(2026, 1, 1))

        assert repo.list_active() == []
