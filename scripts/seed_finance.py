"""
Seed script — populate the finance tables with realistic-looking data
for the current month and the previous one, so the UI has something to show.

Idempotent: aborts if any account, category, or transaction already exists.
Run with:  python -m scripts.seed_finance
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from lifemanager.core.config.database import get_session
from lifemanager.finance.models import (
    Account,
    AccountType,
    Category,
    Debt,
    DebtStatus,
    FlowType,
    GoalStatus,
    GrandType,
    NatureType,
    SavingsGoal,
    SenseType,
    Transaction,
)


def _abort_if_already_seeded(session) -> bool:
    for model in (Account, Category, Transaction):
        count = session.scalar(select(model).limit(1))
        if count is not None:
            return True
    return False


def _previous_month(today: date) -> tuple[int, int]:
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def main() -> None:
    today = date.today()
    prev_y, prev_m = _previous_month(today)

    with get_session() as session:
        if _abort_if_already_seeded(session):
            print("⚠  Données existantes détectées — seed annulé pour éviter les doublons.")
            return

        # ── Accounts ─────────────────────────────────────────────────────────
        courant = Account(
            name="Compte courant",
            type=AccountType.COURANT.value,
            initial_balance=Decimal("500.00"),
        )
        epargne = Account(
            name="Livret A",
            type=AccountType.EPARGNE.value,
            initial_balance=Decimal("2000.00"),
        )
        liquide = Account(
            name="Liquide",
            type=AccountType.LIQUIDE.value,
            initial_balance=Decimal("80.00"),
        )
        session.add_all([courant, epargne, liquide])
        session.flush()

        # ── Categories ───────────────────────────────────────────────────────
        cat_salaire = Category(
            name="Salaire",
            grand_type=GrandType.REVENU.value,
            nature=NatureType.FIXE.value,
        )
        cat_alim = Category(
            name="Alimentation",
            grand_type=GrandType.DEPENSE.value,
            nature=NatureType.VARIABLE.value,
        )
        cat_loisirs = Category(
            name="Loisirs",
            grand_type=GrandType.DEPENSE.value,
            nature=NatureType.VARIABLE.value,
        )
        cat_loyer = Category(
            name="Loyer",
            grand_type=GrandType.DEPENSE.value,
            nature=NatureType.FIXE.value,
        )
        cat_transport = Category(
            name="Transport",
            grand_type=GrandType.DEPENSE.value,
            nature=NatureType.VARIABLE.value,
        )
        session.add_all([cat_salaire, cat_alim, cat_loisirs, cat_loyer, cat_transport])
        session.flush()

        # ── A debt and a savings goal so DETTE/EPARGNE flows have a target ──
        debt = Debt(
            name="Prêt voiture",
            debt_type="Crédit consommation",
            initial_amount=Decimal("8000.00"),
            current_balance=Decimal("5400.00"),
            monthly_target=Decimal("220.00"),
            status=DebtStatus.ACTIVE.value,
            started_at=date(2024, 6, 1),
        )
        goal = SavingsGoal(
            name="Vacances été",
            target_amount=Decimal("1500.00"),
            current_amount=Decimal("450.00"),
            monthly_target=Decimal("150.00"),
            target_date=date(today.year, 7, 1),
            status=GoalStatus.ACTIF.value,
        )
        session.add_all([debt, goal])
        session.flush()

        # ── Transactions: previous month ─────────────────────────────────────
        prev_rows = [
            (date(prev_y, prev_m, 3), Decimal("1800.00"), FlowType.REVENU,
             SenseType.ENTREE, "Salaire", courant, cat_salaire, None, None),
            (date(prev_y, prev_m, 5), Decimal("750.00"), FlowType.DEPENSE,
             SenseType.SORTIE, "Loyer avril", courant, cat_loyer, None, None),
            (date(prev_y, prev_m, 8), Decimal("62.40"), FlowType.DEPENSE,
             SenseType.SORTIE, "Courses Lidl", courant, cat_alim, None, None),
            (date(prev_y, prev_m, 14), Decimal("220.00"), FlowType.DETTE,
             SenseType.SORTIE, "Mensualité prêt voiture", courant, None, debt, None),
            (date(prev_y, prev_m, 20), Decimal("150.00"), FlowType.EPARGNE,
             SenseType.SORTIE, "Virement Livret A", courant, None, None, goal),
        ]

        # ── Transactions: current month ──────────────────────────────────────
        curr_rows = [
            (date(today.year, today.month, 3), Decimal("1800.00"), FlowType.REVENU,
             SenseType.ENTREE, "Salaire", courant, cat_salaire, None, None),
            (date(today.year, today.month, 5), Decimal("750.00"), FlowType.DEPENSE,
             SenseType.SORTIE, "Loyer", courant, cat_loyer, None, None),
            (date(today.year, today.month, 1), Decimal("45.30"), FlowType.DEPENSE,
             SenseType.SORTIE, "Courses Lidl", courant, cat_alim, None, None),
            (date(today.year, today.month, 4), Decimal("28.00"), FlowType.DEPENSE,
             SenseType.SORTIE, "Cinéma", courant, cat_loisirs, None, None),
            (date(today.year, today.month, 2), Decimal("15.20"), FlowType.DEPENSE,
             SenseType.SORTIE, "Métro", liquide, cat_transport, None, None),
            (date(today.year, today.month, 6), Decimal("220.00"), FlowType.DETTE,
             SenseType.SORTIE, "Mensualité prêt voiture", courant, None, debt, None),
            (date(today.year, today.month, 6), Decimal("150.00"), FlowType.EPARGNE,
             SenseType.SORTIE, "Virement Livret A", courant, None, None, goal),
        ]

        for d, amount, flow, sense, label, account, category, debt_ref, goal_ref in (
            prev_rows + curr_rows
        ):
            session.add(
                Transaction(
                    date=d,
                    amount=amount,
                    flow_type=flow.value,
                    sense=sense.value,
                    label=label,
                    account_id=account.id,
                    category_id=category.id if category is not None else None,
                    debt_id=debt_ref.id if debt_ref is not None else None,
                    goal_id=goal_ref.id if goal_ref is not None else None,
                )
            )

    print("✅  Seed terminé.")
    print(f"   - 3 comptes, 5 catégories, 1 dette, 1 objectif d'épargne")
    print(f"   - {len(prev_rows)} transactions sur {prev_y}-{prev_m:02d}")
    print(f"   - {len(curr_rows)} transactions sur {today.year}-{today.month:02d}")


if __name__ == "__main__":
    main()
