"""
Application entry point.
Run with:  python -m lifemanager
Or after install:  lifemanager
"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from lifemanager.finance.controllers import FinanceController
from lifemanager.finance.views import TransactionsView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LifeManager — Gestion vie personnelle")
        self.setMinimumSize(1200, 800)

        self.finance_controller = FinanceController(self)
        self.transactions_view = TransactionsView(self.finance_controller, self)
        self.setCentralWidget(self.transactions_view)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LifeManager")
    app.setOrganizationName("Personal")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
