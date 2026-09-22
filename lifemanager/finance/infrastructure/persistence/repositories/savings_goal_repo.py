"""SavingsGoalRepository — DB access for SavingsGoal entities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from lifemanager.finance.application.dto import SavingsGoalReadDTO
from lifemanager.finance.domain.enums import GoalStatus
from lifemanager.finance.models import SavingsGoal


class SavingsGoalRepository:
    model = SavingsGoal

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self) -> list[SavingsGoal]:
        stmt = (
            select(SavingsGoal)
            .where(SavingsGoal.status == GoalStatus.ACTIF.value)
            .order_by(SavingsGoal.target_date)
        )
        return list(self._session.scalars(stmt))

    def list_active_read(self) -> list[SavingsGoalReadDTO]:
        """Return active savings goals without exposing ORM instances."""
        return [self._to_read_dto(goal) for goal in self.list_active()]

    @staticmethod
    def _to_read_dto(goal: SavingsGoal) -> SavingsGoalReadDTO:
        return SavingsGoalReadDTO(
            id=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            monthly_target=goal.monthly_target,
            target_date=goal.target_date,
            status=goal.status,
        )
