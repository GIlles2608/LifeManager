"""SavingsGoalRepository — DB access for SavingsGoal entities."""
from __future__ import annotations

from sqlalchemy import select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.models import GoalStatus, SavingsGoal


class SavingsGoalRepository(BaseRepository[SavingsGoal]):
    model = SavingsGoal

    def list_active(self) -> list[SavingsGoal]:
        stmt = (
            select(SavingsGoal)
            .where(SavingsGoal.status == GoalStatus.ACTIF.value)
            .order_by(SavingsGoal.target_date)
        )
        return list(self._session.scalars(stmt))
