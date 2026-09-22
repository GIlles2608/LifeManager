"""Bank account domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Account:
    """A financial account and its opening balance."""

    id: uuid.UUID
    name: str
    type: str
    initial_balance: Decimal
    is_active: bool
