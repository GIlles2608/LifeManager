"""Input DTOs accepted by Finance application services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from lifemanager.finance.domain.enums import FlowType, SenseType


@dataclass(frozen=True)
class TransactionDTO:
    """Validated transaction input from presentation to the service."""

    date: date
    amount: Decimal
    flow_type: FlowType
    sense: SenseType
    label: str
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    debt_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
