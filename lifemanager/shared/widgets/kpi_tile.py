"""KpiTile — small labeled value tile for KPI bands."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


class KpiTile(QFrame):
    """A title + value box. Use set_value() to update; set_tone() to color it."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(140)

        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")

        self._value = QLabel("—")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def set_tone(self, tone: str) -> None:
        """tone in {'neutral', 'positive', 'negative'}."""
        colors = {
            "neutral":  "#ffffff",
            "positive": "#4ade80",   # green-400 — readable on dark bg
            "negative": "#f87171",   # red-400 — readable on dark bg
        }
        color = colors.get(tone, "#ffffff")
        self._value.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {color};")
