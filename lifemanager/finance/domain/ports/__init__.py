from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Generic, Protocol, TypeVar

from lifemanager.finance.models import (
    Account,
    Budget,
    Category,
    Debt,
    FlowType,
    SavingsGoal,
    Transaction,
)

T = TypeVar("T")


class BaseRepositoryPort(Protocol, Generic[T]):
    def add(self, entity: T) -> T: ...

    def delete(self, entity_id: uuid.UUID) -> None: ...

    def get_by_id(self, entity_id: uuid.UUID) -> T: ...

    def find_by_id(self, entity_id: uuid.UUID) -> T | None: ...

    def list_all(self) -> list[T]: ...


class TransactionRepositoryPort(BaseRepositoryPort[Transaction], Protocol):
    def list_by_month_with_relations(self, month: str) -> list[Transaction]: ...

    def total_spent_by_category(self, category_id: uuid.UUID, month: str) -> Decimal: ...

    def total_by_flow(self, flow_type: FlowType, month: str) -> Decimal: ...


class BudgetRepositoryPort(BaseRepositoryPort[Budget], Protocol):
    def get_by_category_and_month(self, category_id: uuid.UUID, month: str) -> Budget | None: ...


class CategoryRepositoryPort(BaseRepositoryPort[Category], Protocol):
    def find_by_id(self, entity_id: uuid.UUID) -> Category | None: ...

    def list_active(self) -> list[Category]: ...


class DebtRepositoryPort(BaseRepositoryPort[Debt], Protocol):
    def find_by_id(self, entity_id: uuid.UUID) -> Debt | None: ...

    def list_active(self) -> list[Debt]: ...


class AccountRepositoryPort(BaseRepositoryPort[Account], Protocol):
    def list_active(self) -> list[Account]: ...


class SavingsGoalRepositoryPort(BaseRepositoryPort[SavingsGoal], Protocol):
    def list_active(self) -> list[SavingsGoal]: ...
