"""
TransactionsView — main finance view.

Layout (top to bottom):
- Header: title + month selector
- KPI band: Revenus / Dépenses / Épargne / Dettes / Net
- Toolbar: "Nouvelle..." button (right-aligned)
- Table: transactions for the selected month
- Footer: "Supprimer la transaction sélectionnée" button (right-aligned)

Step 2: read-only data flow wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from lifemanager.core.utils.formatting import format_amount
from lifemanager.finance.application.dto import TransactionReadDTO
from lifemanager.finance.controllers import FinanceController
from lifemanager.finance.services.finance_service import MonthlyKPIs
from lifemanager.finance.views.add_transaction_dialog import AddTransactionDialog
from lifemanager.finance.views.transaction_table_model import TransactionTableModel
from lifemanager.shared.widgets.kpi_tile import KpiTile


class TransactionsView(QWidget):
    KPI_LABELS = ("Revenus", "Dépenses", "Épargne", "Dettes", "Net")
    MONTHS_HISTORY = 12  # months shown in the selector before the current one

    def __init__(self, controller: FinanceController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._build_ui()
        self._connect_signals()
        self._populate_month_combo()
        self._refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        root.addLayout(self._build_kpi_band())
        root.addLayout(self._build_toolbar())
        root.addWidget(self._build_table(), stretch=1)
        root.addLayout(self._build_footer())

    def _build_header(self) -> QHBoxLayout:
        title = QLabel("Finances")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")

        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(180)

        h = QHBoxLayout()
        h.addWidget(title)
        h.addStretch(1)
        h.addWidget(QLabel("Mois :"))
        h.addWidget(self.month_combo)
        return h

    def _build_kpi_band(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(8)
        self.kpi_tiles: dict[str, KpiTile] = {}
        for label in self.KPI_LABELS:
            tile = KpiTile(label)
            self.kpi_tiles[label] = tile
            h.addWidget(tile, stretch=1)
        return h

    def _build_toolbar(self) -> QHBoxLayout:
        self.add_button = QPushButton("+ Nouvelle…")

        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(self.add_button)
        return h

    def _build_table(self) -> QTableView:
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        vertical_header = self.table.verticalHeader()
        assert vertical_header is not None
        vertical_header.setVisible(False)

        self.model = TransactionTableModel(self.table)
        self.table.setModel(self.model)

        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            TransactionTableModel.COL_DATE, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_AMOUNT, QHeaderView.ResizeMode.ResizeToContents
        )
        return self.table

    def _build_footer(self) -> QHBoxLayout:
        self.delete_button = QPushButton("Supprimer la transaction sélectionnée")
        self.delete_button.setEnabled(False)  # toggled by selection

        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(self.delete_button)
        return h

    # ── Wiring ────────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        selection_model = self.table.selectionModel()
        assert selection_model is not None
        selection_model.selectionChanged.connect(self._on_selection_changed)
        self._controller.kpis_refreshed.connect(self._on_kpis_refreshed)
        self._controller.transaction_created.connect(self._on_transaction_created)
        self._controller.transaction_deleted.connect(self._on_transaction_deleted)
        self._controller.error.connect(self._on_error)

    def _populate_month_combo(self) -> None:
        """Fill with the last MONTHS_HISTORY months ending on the current month."""
        today = datetime.now(UTC).date()
        months: list[str] = []
        y, m = today.year, today.month
        for _ in range(self.MONTHS_HISTORY):
            months.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1

        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        for ym in months:
            self.month_combo.addItem(ym, userData=ym)
        self.month_combo.setCurrentIndex(0)  # current month
        self.month_combo.blockSignals(False)

    # ── Refresh logic ─────────────────────────────────────────────────────────

    def _selected_month(self) -> str:
        return cast(str, self.month_combo.currentData())

    def _refresh(self) -> None:
        month = self._selected_month()
        if not month:
            return
        # KPIs refresh emits kpis_refreshed -> handled in _on_kpis_refreshed
        self._controller.get_monthly_kpis(month)
        # Transactions: no signal, direct return
        rows = self._controller.list_transactions(month) or []
        self.model.set_transactions(rows)
        # Reset clears selection — keep delete button in sync.
        self.delete_button.setEnabled(False)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_month_changed(self, _index: int) -> None:
        self._refresh()

    def _on_transaction_created(self, _tx: TransactionReadDTO) -> None:
        self._refresh()

    def _on_transaction_deleted(self, _tx_id: uuid.UUID) -> None:
        self._refresh()

    def _on_add_clicked(self) -> None:
        dialog = AddTransactionDialog(self._controller, self)
        if dialog.exec() != AddTransactionDialog.DialogCode.Accepted:
            return
        dto = dialog.dto()
        if dto is None:
            return
        self._controller.create_transaction(dto)
        # Success/failure handled via transaction_created / error signals.

    def _on_selection_changed(self, *_args: object) -> None:
        self.delete_button.setEnabled(self._selected_transaction() is not None)

    def _on_delete_clicked(self) -> None:
        tx = self._selected_transaction()
        if tx is None:
            return
        confirm = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Supprimer la transaction « {tx.label} » ({format_amount(tx.amount, signed=False)}) ?\n"
            "Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._controller.delete_transaction(tx.id)
        # Success/failure handled via transaction_deleted / error signals.

    def _selected_transaction(self) -> TransactionReadDTO | None:
        selection_model = self.table.selectionModel()
        assert selection_model is not None
        indexes = selection_model.selectedRows()
        if not indexes:
            return None
        return self.model.transaction_at(indexes[0].row())

    def _on_kpis_refreshed(self, kpis: MonthlyKPIs) -> None:
        self._set_tile("Revenus", kpis.revenues, tone="positive")
        self._set_tile("Dépenses", kpis.expenses, tone="negative")
        self._set_tile("Épargne", kpis.savings, tone="neutral")
        self._set_tile("Dettes", kpis.debt_repayments, tone="neutral")

        net_tone = "positive" if kpis.net >= 0 else "negative"
        self._set_tile("Net", kpis.net, tone=net_tone, signed=True)

    def _set_tile(
        self,
        label: str,
        value: Decimal,
        *,
        tone: str,
        signed: bool = False,
    ) -> None:
        tile = self.kpi_tiles[label]
        tile.set_value(format_amount(value, signed=signed))
        tile.set_tone(tone)

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Erreur", message)
