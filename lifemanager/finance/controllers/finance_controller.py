"""
FinanceController — bridges PyQt6 views and FinanceService.

Responsibilities:
- Open/close a SQLAlchemy session per user action (Pattern B Unit-of-Work).
- Catch domain errors and surface them as Qt signals so views never see exceptions.
- Re-emit useful events as Qt signals for direct view binding.

Inter-module notifications (e.g. Dashboard refresh on TRANSACTION_CREATED) keep
flowing through the global event bus, emitted by the service layer.
"""
from __future__ import annotations

import uuid
from typing import Callable, TypeVar

from PyQt6.QtCore import QObject, pyqtSignal

from lifemanager.core.config.database import get_session
from lifemanager.core.exceptions.exceptions import LifeManagerError
from lifemanager.finance.models import Account, Category, Debt, SavingsGoal, Transaction
from lifemanager.finance.services.finance_service import (
    BudgetCheckResult,
    FinanceService,
    MonthlyKPIs,
    TransactionDTO,
)

T = TypeVar("T")


class FinanceController(QObject):
    """Sync entry points for views; signals for outbound notifications."""

    # ── Outbound signals (views connect to these) ─────────────────────────────
    transaction_created = pyqtSignal(object)   # Transaction
    transaction_deleted = pyqtSignal(object)   # uuid.UUID
    kpis_refreshed      = pyqtSignal(object)   # MonthlyKPIs
    budget_checked      = pyqtSignal(object)   # BudgetCheckResult
    debt_updated        = pyqtSignal()         # no payload — view re-fetches
    error               = pyqtSignal(str)      # human-readable message

    # ── Public API ────────────────────────────────────────────────────────────

    def create_transaction(self, dto: TransactionDTO) -> Transaction | None:
        """Create a transaction. Returns None on validation/persistence error."""
        def op(svc: FinanceService) -> Transaction:
            return svc.create_transaction(dto)

        tx = self._run(op)
        if tx is not None:
            self.transaction_created.emit(tx)
        return tx

    def delete_transaction(self, transaction_id: uuid.UUID) -> bool:
        """Returns True on success, False on error."""
        def op(svc: FinanceService) -> uuid.UUID:
            svc.delete_transaction(transaction_id)
            return transaction_id

        result = self._run(op)
        if result is not None:
            self.transaction_deleted.emit(result)
            return True
        return False

    def get_monthly_kpis(self, month: str) -> MonthlyKPIs | None:
        def op(svc: FinanceService) -> MonthlyKPIs:
            return svc.get_monthly_kpis(month)

        kpis = self._run(op)
        if kpis is not None:
            self.kpis_refreshed.emit(kpis)
        return kpis

    def list_transactions(self, month: str) -> list[Transaction] | None:
        """Returns transactions for the month, or None on error."""
        def op(svc: FinanceService) -> list[Transaction]:
            return svc.list_transactions(month)

        return self._run(op)

    # ── Lookups (used to populate selectors in dialogs) ───────────────────────

    def list_accounts(self) -> list[Account]:
        return self._run(lambda svc: svc.list_accounts()) or []

    def list_categories(self) -> list[Category]:
        return self._run(lambda svc: svc.list_categories()) or []

    def list_active_debts(self) -> list[Debt]:
        return self._run(lambda svc: svc.list_active_debts()) or []

    def list_active_goals(self) -> list[SavingsGoal]:
        return self._run(lambda svc: svc.list_active_goals()) or []

    def check_budget(
        self, category_id: uuid.UUID, month: str
    ) -> BudgetCheckResult | None:
        def op(svc: FinanceService) -> BudgetCheckResult:
            return svc.check_budget(category_id, month)

        result = self._run(op)
        if result is not None:
            self.budget_checked.emit(result)
        return result

    def update_debt_balance(
        self, debt_id: uuid.UUID, new_balance
    ) -> bool:
        def op(svc: FinanceService) -> bool:
            svc.update_debt_balance(debt_id, new_balance)
            return True

        if self._run(op):
            self.debt_updated.emit()
            return True
        return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self, op: Callable[[FinanceService], T]) -> T | None:
        """
        Run a service operation in a fresh session (Pattern B Unit-of-Work):
        get_session() commits on success, rolls back on exception.

        Domain errors (LifeManagerError subclasses) are caught and surfaced
        via the `error` signal; the method then returns None so the view can
        check for the failure case without try/except.

        Unexpected exceptions propagate — they indicate bugs and should crash
        loud rather than silently turn into "operation failed".
        """
        try:
            with get_session() as session:
                return op(FinanceService(session))
        except LifeManagerError as e:
            self.error.emit(str(e))
            return None
