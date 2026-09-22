"""Transaction category domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """A category optionally linked to a parent category."""

    id: uuid.UUID
    name: str
    grand_type: str
    nature: str
    is_active: bool
    parent_id: uuid.UUID | None
