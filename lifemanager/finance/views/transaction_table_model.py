"""
TransactionTableModel — adapts a list[Transaction] for QTableView.

Read-only at this stage (set in TransactionsView via NoEditTriggers).
Use set_transactions() to replace the underlying data; the view is reset
via beginResetModel/endResetModel.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt

from lifemanager.core.utils.formatting import format_amount, format_short_date
from lifemanager.finance.application.dto import TransactionReadDTO
from lifemanager.finance.domain.enums import SenseType


class TransactionTableModel(QAbstractTableModel):
    HEADERS = ("Date", "Libellé", "Catégorie", "Compte", "Montant")
    COL_DATE, COL_LABEL, COL_CATEGORY, COL_ACCOUNT, COL_AMOUNT = range(5)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[TransactionReadDTO] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def set_transactions(self, rows: list[TransactionReadDTO]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def transaction_at(self, row: int) -> TransactionReadDTO | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    # ── Qt model interface ────────────────────────────────────────────────────

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        index = parent if parent is not None else QModelIndex()
        return 0 if index.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        index = parent if parent is not None else QModelIndex()
        return 0 if index.isValid() else len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        tx = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_DATE:
                return format_short_date(tx.date)
            if col == self.COL_LABEL:
                return tx.label
            if col == self.COL_CATEGORY:
                return tx.category_name or "—"
            if col == self.COL_ACCOUNT:
                return tx.account_name
            if col == self.COL_AMOUNT:
                signed = tx.amount if tx.sense == SenseType.ENTREE.value else -tx.amount
                return format_amount(Decimal(signed))

        if role == Qt.ItemDataRole.TextAlignmentRole and col == self.COL_AMOUNT:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ForegroundRole and col == self.COL_AMOUNT:
            from PyQt6.QtGui import QColor

            if tx.sense == SenseType.ENTREE.value:
                return QColor("#1b7a3e")
            return QColor("#b3261e")

        return None
