"""
AddTransactionDialog — modal form to create a new Transaction.

Category is a transverse tag — it can be attached to any flow_type, optionally.
Extra targeting fields are shown depending on the FlowType:
- DETTE      →  debt selector visible (and required)
- EPARGNE    →  savings-goal selector visible (and required)
- others     →  neither

UI-side validation is intentionally minimal: only "required field is filled".
Business rules (amount > 0, blank label, etc.) are enforced by FinanceService
and surfaced via the controller's `error` signal.
"""
from __future__ import annotations

from decimal import Decimal

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from lifemanager.finance.controllers import FinanceController
from lifemanager.finance.models import FlowType, SenseType
from lifemanager.finance.services.finance_service import TransactionDTO


class AddTransactionDialog(QDialog):
    """Returns a TransactionDTO via .dto() if accepted, None otherwise."""

    def __init__(
        self,
        controller: FinanceController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Nouvelle transaction")
        self.setModal(True)
        self.setMinimumWidth(420)

        self._dto: TransactionDTO | None = None

        self._build_ui()
        self._populate_combos()
        self._connect_signals()
        self._on_flow_type_changed()  # initial visibility sync

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        self.amount_edit = QDoubleSpinBox()
        self.amount_edit.setDecimals(2)
        self.amount_edit.setMinimum(0.01)
        self.amount_edit.setMaximum(1_000_000.00)
        self.amount_edit.setSingleStep(1.00)
        self.amount_edit.setSuffix(" €")
        self.amount_edit.setValue(0.01)

        self.flow_combo = QComboBox()
        for ft in FlowType:
            self.flow_combo.addItem(ft.value.capitalize(), userData=ft)

        self.sense_combo = QComboBox()
        for s in SenseType:
            self.sense_combo.addItem(s.value.capitalize(), userData=s)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Ex. : Courses Lidl")

        self.account_combo = QComboBox()
        self.category_combo = QComboBox()
        self.debt_combo = QComboBox()
        self.goal_combo = QComboBox()

        # Build form rows; we keep a handle on label widgets for visibility toggling.
        form.addRow("Date :", self.date_edit)
        form.addRow("Montant :", self.amount_edit)
        form.addRow("Type de flux :", self.flow_combo)
        form.addRow("Sens :", self.sense_combo)
        form.addRow("Libellé :", self.label_edit)
        form.addRow("Compte :", self.account_combo)

        form.addRow("Catégorie :", self.category_combo)
        self._debt_label = self._labelled_row(form, "Dette :", self.debt_combo)
        self._goal_label = self._labelled_row(form, "Objectif :", self.goal_combo)

        root.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Ajouter")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        root.addWidget(self.buttons)

    @staticmethod
    def _labelled_row(form: QFormLayout, label: str, widget: QWidget):
        """Add a row and return the auto-created label widget so we can toggle visibility."""
        form.addRow(label, widget)
        return form.labelForField(widget)

    # ── Population ────────────────────────────────────────────────────────────

    def _populate_combos(self) -> None:
        self.account_combo.clear()
        for account in self._controller.list_accounts():
            self.account_combo.addItem(account.name, userData=account.id)

        self.category_combo.clear()
        self.category_combo.addItem("(aucune)", userData=None)
        for cat in self._controller.list_categories():
            self.category_combo.addItem(cat.name, userData=cat.id)

        self.debt_combo.clear()
        for debt in self._controller.list_active_debts():
            self.debt_combo.addItem(debt.name, userData=debt.id)

        self.goal_combo.clear()
        for goal in self._controller.list_active_goals():
            self.goal_combo.addItem(goal.name, userData=goal.id)

    # ── Signals ───────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.flow_combo.currentIndexChanged.connect(self._on_flow_type_changed)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

    # ── Visibility logic ──────────────────────────────────────────────────────

    def _current_flow_type(self) -> FlowType:
        return self.flow_combo.currentData()

    def _on_flow_type_changed(self) -> None:
        ft = self._current_flow_type()

        show_debt = ft == FlowType.DETTE
        show_goal = ft == FlowType.EPARGNE

        # Category stays visible for every flow_type — it's a transverse tag.
        self._set_row_visible(self._debt_label, self.debt_combo, show_debt)
        self._set_row_visible(self._goal_label, self.goal_combo, show_goal)

        # Default sense: REVENU = ENTREE, otherwise SORTIE — user can still override.
        default_sense = SenseType.ENTREE if ft == FlowType.REVENU else SenseType.SORTIE
        idx = self.sense_combo.findData(default_sense)
        if idx >= 0:
            self.sense_combo.setCurrentIndex(idx)

    @staticmethod
    def _set_row_visible(label: QWidget | None, field: QWidget, visible: bool) -> None:
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    # ── Accept ────────────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        # Minimal UI checks — service does the real validation.
        if not self.label_edit.text().strip():
            QMessageBox.warning(self, "Champ requis", "Le libellé est obligatoire.")
            return
        if self.account_combo.currentData() is None:
            QMessageBox.warning(self, "Champ requis", "Sélectionnez un compte.")
            return

        ft: FlowType = self._current_flow_type()
        if ft == FlowType.DETTE and self.debt_combo.currentData() is None:
            QMessageBox.warning(self, "Champ requis", "Sélectionnez une dette.")
            return
        if ft == FlowType.EPARGNE and self.goal_combo.currentData() is None:
            QMessageBox.warning(self, "Champ requis", "Sélectionnez un objectif.")
            return

        py_date = self.date_edit.date().toPyDate()
        amount = Decimal(str(self.amount_edit.value()))

        category_id = self.category_combo.currentData()  # may be None ("(aucune)")
        debt_id = self.debt_combo.currentData() if ft == FlowType.DETTE else None
        goal_id = self.goal_combo.currentData() if ft == FlowType.EPARGNE else None

        self._dto = TransactionDTO(
            date=py_date,
            amount=amount,
            flow_type=ft,
            sense=self.sense_combo.currentData(),
            label=self.label_edit.text().strip(),
            account_id=self.account_combo.currentData(),
            category_id=category_id,
            debt_id=debt_id,
            goal_id=goal_id,
        )
        self.accept()

    # ── Public API ────────────────────────────────────────────────────────────

    def dto(self) -> TransactionDTO | None:
        """Return the DTO if the user clicked OK and validation passed."""
        return self._dto
