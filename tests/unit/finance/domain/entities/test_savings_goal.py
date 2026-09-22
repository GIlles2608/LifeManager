from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from lifemanager.finance.domain.entities import SavingsGoal


def make_goal(target: Decimal = Decimal(1000), current: Decimal = Decimal(250)) -> SavingsGoal:
    return SavingsGoal(
        id=uuid.uuid4(),
        name="Voyage",
        target_amount=target,
        current_amount=current,
        monthly_target=Decimal(100),
        target_date=date(2027, 1, 1),
        status="actif",
    )


def test_goal_calculates_remaining_and_progress() -> None:
    goal = make_goal()

    assert goal.remaining == Decimal(750)
    assert goal.progress == 0.25


def test_goal_progress_is_zero_for_zero_target() -> None:
    assert make_goal(target=Decimal(0), current=Decimal(0)).progress == 0.0
