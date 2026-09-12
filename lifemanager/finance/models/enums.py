"""Finance domain enums — shared across all finance models."""
from __future__ import annotations

from enum import Enum


class FlowType(str, Enum):
    REVENU    = "revenu"
    DEPENSE   = "depense"
    TRANSFERT = "transfert"
    DETTE     = "dette"
    EPARGNE   = "epargne"


class SenseType(str, Enum):
    ENTREE = "entree"
    SORTIE = "sortie"


class AccountType(str, Enum):
    COURANT = "courant"
    EPARGNE = "epargne"
    LIQUIDE = "liquide"


class GrandType(str, Enum):
    REVENU    = "revenu"
    DEPENSE   = "depense"
    EPARGNE   = "epargne"
    DETTE     = "dette"
    TRANSFERT = "transfert"


class NatureType(str, Enum):
    FIXE     = "fixe"
    VARIABLE = "variable"
    NA       = "na"


class DebtStatus(str, Enum):
    ACTIVE    = "active"
    SOLDEE    = "soldee"
    SUSPENDUE = "suspendue"


class GoalStatus(str, Enum):
    ACTIF     = "actif"
    ATTEINT   = "atteint"
    ABANDONNE = "abandonne"
