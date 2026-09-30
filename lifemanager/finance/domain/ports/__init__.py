from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Protocol

from lifemanager.core.ports.event_publisher import EventCollectingRepository
from lifemanager.finance.application.dto import (
    AccountReadDTO,
    CategoryReadDTO,
    DebtReadDTO,
    SavingsGoalReadDTO,
    TransactionReadDTO,
)
from lifemanager.finance.domain.entities import (
    Budget,
    Debt,
)
from lifemanager.finance.domain.entities import (
    Transaction as TransactionEntity,
)
from lifemanager.finance.domain.enums import FlowType


class TransactionRepositoryPort(EventCollectingRepository, Protocol):
    """Persists transactions and collects the events they record."""

    def add(self, entity: TransactionEntity) -> TransactionEntity: ...

    def delete(self, entity_id: uuid.UUID) -> None: ...

    def list_by_month_with_relations(self, month: str) -> list[TransactionReadDTO]: ...

    def read_by_id(self, transaction_id: uuid.UUID) -> TransactionReadDTO | None: ...

    def total_spent_by_category(self, category_id: uuid.UUID, month: str) -> Decimal: ...

    def total_by_flow(self, flow_type: FlowType, month: str) -> Decimal: ...


class BudgetRepositoryPort(EventCollectingRepository, Protocol):
    """Reads budgets and collects the events they record."""

    def get_by_category_and_month(self, category_id: uuid.UUID, month: str) -> Budget | None: ...


class CategoryRepositoryPort(Protocol):
    def list_active_read(self) -> list[CategoryReadDTO]: ...

    def find_read_by_id(self, entity_id: uuid.UUID) -> CategoryReadDTO | None: ...


class DebtRepositoryPort(EventCollectingRepository, Protocol):
    """Persists debts and collects the events they record."""

    def find_domain_by_id(self, entity_id: uuid.UUID) -> Debt | None: ...

    def save_domain(self, entity: Debt) -> Debt: ...

    def list_active_read(self) -> list[DebtReadDTO]: ...


class AccountRepositoryPort(Protocol):
    def list_active_read(self) -> list[AccountReadDTO]: ...


class SavingsGoalRepositoryPort(Protocol):
    def list_active_read(self) -> list[SavingsGoalReadDTO]: ...
