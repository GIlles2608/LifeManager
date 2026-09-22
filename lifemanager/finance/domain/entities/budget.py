"""Monthly budget domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Budget:
    """Spending ceiling for one category and month."""

    id: uuid.UUID
    month: str
    ceiling: Decimal
    category_id: uuid.UUID
