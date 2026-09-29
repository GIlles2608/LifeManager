"""Application composition root."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PyQt6.QtWidgets import QApplication, QMainWindow

from lifemanager.finance.controllers import FinanceController
from lifemanager.finance.infrastructure.bootstrap import build_finance_service
from lifemanager.finance.views import TransactionsView


class MainWindow(QMainWindow):
    """Main application window composed with its application services."""

    def __init__(self, finance_controller: FinanceController) -> None:
        super().__init__()
        self.setWindowTitle("LifeManager — Gestion vie personnelle")
        self.setMinimumSize(1200, 800)
        self.finance_controller = finance_controller
        self.transactions_view = TransactionsView(self.finance_controller, self)
        self.setCentralWidget(self.transactions_view)


class Application:
    """Own the Qt event loop and the resources assembled for the application."""

    def __init__(self, qt_application: QApplication, window: MainWindow) -> None:
        self._qt_application = qt_application
        self._window = window

    def run(self) -> int:
        """Show the main window and run the Qt event loop."""
        self._window.show()
        return self._qt_application.exec()


def build_application(argv: Sequence[str] | None = None) -> Application:
    """Compose the Qt application, Finance service, controller, and window.

    No database session is opened here: the Finance service opens one per
    operation through its unit-of-work factory.
    """
    qt_application = QApplication(list(sys.argv if argv is None else argv))
    qt_application.setApplicationName("LifeManager")
    qt_application.setOrganizationName("Personal")

    service = build_finance_service()
    controller = FinanceController(service)
    window = MainWindow(controller)
    return Application(qt_application, window)
