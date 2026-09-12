"""Locale-aware formatters used across the UI."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from babel.dates import format_date
from babel.numbers import format_currency as _babel_format_currency

from lifemanager.core.config.settings import settings


def format_amount(amount: Decimal, *, signed: bool = True) -> str:
    """
    Format a Decimal as a localized currency string.

    `signed=True` keeps the sign Babel produces ("-45,30 €" / "1 200,00 €").
    `signed=False` returns the magnitude only ("45,30 €").
    """
    value = amount if signed else abs(amount)
    return _babel_format_currency(
        value,
        settings.app.currency,
        locale=settings.app.locale,
    )


def format_short_date(d: date) -> str:
    """Render a date in 'dd/MM' — year is implicit from the month context."""
    return format_date(d, format="dd/MM", locale=settings.app.locale)
