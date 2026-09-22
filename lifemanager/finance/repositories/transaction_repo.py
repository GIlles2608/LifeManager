"""
TransactionRepository — DB access for Transaction entities.

Sum semantics:
- total_* methods return unsigned magnitudes (Decimal >= 0). Direction is
  carried by the `sense` column, not by the sign of the returned value.
- cashflow() is the only method that returns a signed value, derived from
  `sense` (ENTREE - SORTIE), independent of `flow_type`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from lifemanager.core.repositories.base import BaseRepository
from lifemanager.finance.application.dto import TransactionReadDTO
from lifemanager.finance.models import Account, Category, FlowType, SenseType, Transaction


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    # ── Read: lists ───────────────────────────────────────────────────────────

    def list_by_month(self, month: str) -> list[Transaction]:
        """All transactions for a YYYY-MM month string."""
        stmt = (
            select(Transaction)
            .where(func.to_char(Transaction.date, "YYYY-MM") == month)
            .order_by(Transaction.date.desc())
        )
        return list(self._session.scalars(stmt))

    def list_by_month_with_relations(self, month: str) -> list[TransactionReadDTO]:
        """Return presentation-ready transactions for a YYYY-MM month."""
        stmt = (
            select(Transaction, Account.name, Category.name)
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(func.to_char(Transaction.date, "YYYY-MM") == month)
            .order_by(Transaction.date.desc())
        )
        return [
            self._to_read_dto(transaction, account_name, category_name)
            for transaction, account_name, category_name in self._session.execute(stmt)
        ]

    def read_by_id(self, transaction_id: uuid.UUID) -> TransactionReadDTO | None:
        """Return one transaction as a flattened DTO, if it exists."""
        stmt = (
            select(Transaction, Account.name, Category.name)
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(Transaction.id == transaction_id)
        )
        row = self._session.execute(stmt).first()
        if row is None:
            return None
        transaction, account_name, category_name = row
        return self._to_read_dto(transaction, account_name, category_name)

    @staticmethod
    def _to_read_dto(
        transaction: Transaction,
        account_name: str,
        category_name: str | None,
    ) -> TransactionReadDTO:
        """Flatten an ORM transaction before it leaves the repository."""
        return TransactionReadDTO(
            id=transaction.id,
            date=transaction.date,
            amount=transaction.amount,
            flow_type=transaction.flow_type,
            sense=transaction.sense,
            label=transaction.label,
            account_id=transaction.account_id,
            account_name=account_name,
            category_id=transaction.category_id,
            category_name=category_name,
            debt_id=transaction.debt_id,
            goal_id=transaction.goal_id,
        )

    def list_by_account(self, account_id: uuid.UUID) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.date.desc())
        )
        return list(self._session.scalars(stmt))

    # ── Read: aggregates ──────────────────────────────────────────────────────

    def total_in(self, month: str) -> Decimal:
        """Σ amount where sense = ENTREE for the given month. Unsigned."""
        return self._sum_amount(
            month=month,
            sense=SenseType.ENTREE,
        )

    def total_out(self, month: str) -> Decimal:
        """Σ amount where sense = SORTIE for the given month. Unsigned."""
        return self._sum_amount(
            month=month,
            sense=SenseType.SORTIE,
        )

    def total_by_flow(self, flow_type: FlowType, month: str) -> Decimal:
        """
        Σ amount filtered by flow_type for the given month. Unsigned.
        Sense is not considered — useful for "how much was tagged as EPARGNE
        this month" regardless of direction.
        """
        return self._sum_amount(
            month=month,
            flow_type=flow_type,
        )

    def total_spent_by_category(self, category_id: uuid.UUID, month: str) -> Decimal:
        """Σ amount of DEPENSE transactions tied to a category for the month."""
        return self._sum_amount(
            month=month,
            flow_type=FlowType.DEPENSE,
            category_id=category_id,
        )

    def cashflow(self, month: str) -> Decimal:
        """
        Net cash movement for the month = total_in - total_out, derived from
        `sense` only. Independent of flow_type.
        Positive = net inflow, negative = net outflow.
        """
        return self.total_in(month) - self.total_out(month)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _sum_amount(
        self,
        *,
        month: str,
        sense: SenseType | None = None,
        flow_type: FlowType | None = None,
        category_id: uuid.UUID | None = None,
    ) -> Decimal:
        """Single aggregation primitive — every total_* method funnels through here."""
        conditions = [func.to_char(Transaction.date, "YYYY-MM") == month]
        if sense is not None:
            conditions.append(Transaction.sense == sense.value)
        if flow_type is not None:
            conditions.append(Transaction.flow_type == flow_type.value)
        if category_id is not None:
            conditions.append(Transaction.category_id == category_id)

        stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(*conditions)
        result = self._session.scalar(stmt) or 0
        return Decimal(str(result))
