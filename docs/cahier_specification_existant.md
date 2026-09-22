# Cahier de spécification de l'existant — LifeManager

> **Version :** v1 (état au 2026-05-08)
> **Périmètre couvert :** module **Finance** (seul module fonctionnel à ce jour)
> **Périmètre planifié, hors champ :** modules Grocery, Nutrition, Dashboard, Settings (stubs présents mais vides)

---

## 1. Présentation générale

### 1.1 Objectif du produit

LifeManager est une **application desktop mono-utilisateur** de gestion de la vie personnelle, exécutée localement sur le poste de l'utilisateur avec une base PostgreSQL locale. La v1 livre uniquement le **module Finance** : suivi des transactions, KPIs mensuels, contrôle de budget par catégorie.

### 1.2 Acteurs

| Acteur | Description |
|---|---|
| **Utilisateur** | Acteur unique. Pas de multi-utilisateur en v1, pas de gestion de rôles, pas d'authentification. |

### 1.3 Pile technique

| Couche | Outil | Rôle |
|---|---|---|
| UI | PyQt6 | Interface desktop (widgets en code Python, pas de Qt Designer) |
| ORM | SQLAlchemy 2.0 | Mapping Python ↔ base de données |
| Migrations | Alembic | Versionnement du schéma |
| Base | PostgreSQL local | Stockage primaire |
| Config | python-dotenv | Chargement `.env` au démarrage |
| HTTP | requests | (Réservé Open Food Facts — non utilisé en v1) |
| Tests | pytest + pytest-qt | Unitaires + intégration |
| Qualité | ruff, mypy strict | Lint + typage statique |

### 1.4 Architecture en couches

L'application suit un **MVC à 5 couches** avec couches Service et Repository explicites :

```
Vue (PyQt6) ↕ Contrôleur (signaux Qt) ↕ Service (Python pur) ↕ Repository (SQLAlchemy) ↕ PostgreSQL
```

**Règles de couplage strictes :**
- Une vue n'importe **jamais** un repository.
- Un service n'importe **jamais** Qt.
- Chaque couche ne dialogue qu'avec celle directement en dessous.
- Les services **ne touchent jamais** `self._session.query/get/scalars` — tout passe par un repository.
- Les contrôleurs ouvrent une **session fraîche par appel public** (pattern Unit-of-Work « B »), via `core.config.database.get_session()`.

---

## 2. Diagramme de cas d'utilisation

### 2.1 Source

Fichier : [docs/use_case_diagram.puml](use_case_diagram.puml)

### 2.2 Cas d'utilisation disponibles aujourd'hui (Finance)

| Code | Nom | Déclencheur | Résultat attendu |
|---|---|---|---|
| **UC_View** | Consulter les transactions du mois | Ouverture de l'app ou changement de mois | Liste des transactions du mois affichée dans le tableau |
| **UC_PickMonth** | Changer de mois | Sélection dans `month_combo` | Tableau et KPIs rechargés pour le mois choisi |
| **UC_KPIs** | Voir les 5 KPIs mensuels | Inclus systématiquement par UC_View | 5 tuiles : Revenus, Dépenses, Épargne, Dettes, Net |
| **UC_Add** | Ajouter une transaction | Clic sur `+ Nouvelle…` | Nouvelle ligne en base + table et KPIs rechargés |
| **UC_Delete** | Supprimer une transaction | Clic sur `Supprimer la transaction…` après sélection | Ligne supprimée + table et KPIs rechargés |
| **UC_BudgetAlert** | Voir une alerte de dépassement de budget | Extension automatique de UC_Add si `flow=DEPENSE` et plafond dépassé | `QMessageBox` d'avertissement |

### 2.3 Cas de lookup (sous-cas inclus dans UC_Add)

| Code | Nom | Inclusion |
|---|---|---|
| **UC_PickAccount** | Choisir un compte | `<<include>>` — toujours requis |
| **UC_PickCategory** | Choisir une catégorie | `<<include>>` — optionnel mais combo systématiquement peuplé |
| **UC_PickDebt** | Cibler une dette | `<<extend>>` — uniquement si `flow_type=DETTE` |
| **UC_PickGoal** | Cibler un objectif d'épargne | `<<extend>>` — uniquement si `flow_type=EPARGNE` |

### 2.4 Cas planifiés (hors champ v1, indiqués pour traçabilité)

- **Finance** : Modifier une transaction, Saisir un budget mensuel, CRUD Dettes, CRUD Objectifs d'épargne, Voir le solde courant d'un compte
- **Autres modules** : Suivre les courses (Grocery), Suivre la nutrition (Open Food Facts), Tableau de bord agrégé

### 2.5 Notes sur les relations

- `UC_View ..> UC_KPIs : <<include>>` — afficher la liste recharge toujours les KPIs.
- `UC_Add ..> UC_BudgetAlert : <<extend>>` — l'alerte est conditionnelle (dépense + plafond dépassé).
- `UC_Delete ..> UC_View : <<include>>` — la suppression nécessite une sélection préalable dans la table.

---

## 3. Diagramme de classes

### 3.1 Source

Fichier : [docs/class_diagram.puml](class_diagram.puml)

### 3.2 Couche Core (transverse)

#### 3.2.1 `BaseModel` (abstraite)

Tous les modèles persistés héritent de `BaseModel` ([core/models/base.py](../lifemanager/core/models/base.py)) :

| Attribut | Type | Description |
|---|---|---|
| `id` | `UUID` | Clé primaire générée côté Python |
| `created_at` | `datetime` | Horodatage à l'insertion |
| `updated_at` | `datetime` | Horodatage à chaque mise à jour |

#### 3.2.2 `BaseRepository[T]` (générique)

Fichier : [core/repositories/base.py](../lifemanager/core/repositories/base.py)

API commune à tous les repositories :

| Méthode | Signature | Sémantique |
|---|---|---|
| `add` | `(entity: T) -> T` | Insère + `flush()` (jamais `commit()`) |
| `delete` | `(entity_id: UUID) -> None` | Lève `NotFoundError` si l'id n'existe pas |
| `get_by_id` | `(entity_id: UUID) -> T` | Lève `NotFoundError` si absent |
| `find_by_id` | `(entity_id: UUID) -> T \| None` | Retourne `None` si absent |
| `list_all` | `() -> list[T]` | Tous les enregistrements |

Chaque sous-classe fixe l'attribut de classe `model` et ajoute ses requêtes spécifiques.

#### 3.2.3 Bus d'événements

Fichier : [core/events/bus.py](../lifemanager/core/events/bus.py)

| Classe | Rôle |
|---|---|
| `EventBus` | API `on / off / emit` — communication inter-modules sans import direct |
| `Events` (constantes) | `TRANSACTION_CREATED`, `TRANSACTION_DELETED`, `BUDGET_EXCEEDED`, `DEBT_UPDATED`, `GOAL_UPDATED`, `APP_READY`, `SETTINGS_CHANGED` |

#### 3.2.4 Hiérarchie d'exceptions

```
LifeManagerError
├── NotFoundError
├── ValidationError
└── BudgetExceededError
```

Toutes définies dans [core/exceptions/exceptions.py](../lifemanager/core/exceptions/exceptions.py). Le contrôleur attrape uniquement `LifeManagerError` ; les autres exceptions remontent (signal de bug).

### 3.3 Couche Modèles (Finance)

#### 3.3.1 Énumérations (`finance.domain.enums`)

| Enum | Valeurs |
|---|---|
| `FlowType` | `REVENU`, `DEPENSE`, `TRANSFERT`, `DETTE`, `EPARGNE` |
| `SenseType` | `ENTREE`, `SORTIE` |
| `AccountType` | `COURANT`, `EPARGNE`, `LIQUIDE` |
| `GrandType` | `REVENU`, `DEPENSE`, `EPARGNE`, `DETTE`, `TRANSFERT` |
| `NatureType` | `FIXE`, `VARIABLE`, `NA` |
| `DebtStatus` | `ACTIVE`, `SOLDEE`, `SUSPENDUE` |
| `GoalStatus` | `ACTIF`, `ATTEINT`, `ABANDONNE` |

#### 3.3.2 Entités

| Classe | Attributs propres | Dérivés |
|---|---|---|
| `Account` | `name`, `type: AccountType`, `initial_balance`, `is_active` | — (le solde courant est calculé en SQL par le repo) |
| `Category` | `name`, `grand_type`, `nature`, `is_active`, `parent_id?` | — (auto-référence, profondeur max 2) |
| `Transaction` | `date`, `amount`, `flow_type`, `sense`, `label`, FK : `account_id`, `category_id?`, `debt_id?`, `goal_id?` | `signed_amount`, `month` (`YYYY-MM`) |
| `Budget` | `month` (`YYYY-MM`), `ceiling`, FK `category_id` | — |
| `Debt` | `name`, `initial_amount`, `current_balance`, `monthly_target`, `status: DebtStatus` | `repaid`, `progress` |
| `SavingsGoal` | `name`, `target_amount`, `current_amount`, `monthly_target`, `target_date`, `status: GoalStatus` | `remaining`, `progress` |
| `Alert` | `alert_type`, `message`, `is_read`, FK `budget_id?` | — |

#### 3.3.3 Cardinalités

| Relation | Cardinalité |
|---|---|
| `Transaction → Account` | many → 1 (obligatoire) |
| `Transaction → Category` | many → 0..1 (optionnelle, transverse à `flow_type`) |
| `Transaction → Debt` | many → 0..1 (autorisé **uniquement** si `flow_type=DETTE`) |
| `Transaction → SavingsGoal` | many → 0..1 (autorisé **uniquement** si `flow_type=EPARGNE`) |
| `Budget → Category` | many → 1 |
| `Category → Category (parent)` | 0..1 → 0..1 (max 1 niveau de descente) |
| `Alert → Budget` | many → 0..1 |

### 3.4 Couche Repositories (Finance)

| Repository | Méthodes spécifiques |
|---|---|
| `TransactionRepository` | `list_by_month`, `list_by_month_with_relations` (joinedload account+category), `list_by_account`, `total_in`, `total_out`, `total_by_flow`, `total_spent_by_category`, `cashflow` |
| `AccountRepository` | `list_active`, `get_balance(account_id)` (agrégation SQL `CASE WHEN sense=…`) |
| `CategoryRepository` | `list_active`, `list_by_grand_type`, `list_children`, `list_roots` |
| `BudgetRepository` | `get_by_category_and_month`, `list_by_month` |
| `DebtRepository` | `list_active` |
| `SavingsGoalRepository` | `list_active` |

**Sémantique des agrégats** : les `total_*` retournent une **magnitude non signée** (`Decimal >= 0`). Seul `cashflow(month)` est signé (`total_in - total_out`).

### 3.5 Couche Service (Finance)

#### 3.5.1 DTOs (dataclasses gelées)

```
TransactionDTO         { date, amount, flow_type, sense, label,
                         account_id, category_id?, debt_id?, goal_id? }
MonthlyKPIs            { month, revenues, expenses, savings, debt_repayments, net }
BudgetCheckResult      { category_name, ceiling, spent, remaining, is_exceeded }
```

#### 3.5.2 `FinanceService` ([finance/services/finance_service.py](../lifemanager/finance/services/finance_service.py))

| Méthode | Sémantique |
|---|---|
| `create_transaction(dto)` | Valide, persiste, vérifie budget si DEPENSE+catégorie, émet `TRANSACTION_CREATED` (et éventuellement `BUDGET_EXCEEDED`) |
| `delete_transaction(id)` | Supprime, émet `TRANSACTION_DELETED` |
| `list_transactions(month)` | Liste enrichie (joinedload) pour rendu UI |
| `check_budget(category_id, month)` | Compare dépenses réelles au plafond. Pas de budget ⇒ `ceiling=0` et `is_exceeded=False` |
| `get_monthly_kpis(month)` | 5 KPIs. **Net = Revenus − Dépenses − Épargne − Dettes** (cash disponible après allocations engagées, **pas** le cashflow brut) |
| `update_debt_balance(debt_id, new_balance)` | Refuse les valeurs négatives (`ValidationError`), émet `DEBT_UPDATED` |
| `list_accounts/categories/active_debts/active_goals` | Lookups pour peupler les dialogues |

**Règles de validation** (`_validate_transaction`) :
- `amount > 0` strict
- `label` non vide après `strip()`
- `DETTE` ⇒ `debt_id` obligatoire ; `debt_id` interdit pour les autres flow_types
- `EPARGNE` ⇒ `goal_id` obligatoire ; `goal_id` interdit pour les autres flow_types

### 3.6 Couche Contrôleur (Finance)

#### 3.6.1 `FinanceController` ([finance/controllers/finance_controller.py](../lifemanager/finance/controllers/finance_controller.py))

Hérite de `QObject`. Pattern Unit-of-Work « B » : ouvre une session fraîche par appel via `get_session()`.

**Signaux Qt sortants** (les vues s'y abonnent) :

| Signal | Charge utile |
|---|---|
| `transaction_created` | `Transaction` |
| `transaction_deleted` | `uuid.UUID` |
| `kpis_refreshed` | `MonthlyKPIs` |
| `budget_checked` | `BudgetCheckResult` |
| `debt_updated` | (vide — la vue refait son fetch) |
| `error` | `str` (message lisible) |

**Méthodes publiques synchrones** : retournent `None`/`False` quand une `LifeManagerError` est attrapée et émise via `error`. Les bugs (autres exceptions) propagent.

### 3.7 Couche Vue (Finance)

| Classe | Type Qt | Rôle |
|---|---|---|
| `TransactionsView` | `QWidget` | Composant principal : combo mois + 5 `KpiTile` + tableau + boutons add/delete |
| `TransactionTableModel` | `QAbstractTableModel` | Fournit les données du tableau ; `set_transactions(rows)`, `transaction_at(row)` |
| `AddTransactionDialog` | `QDialog` | Formulaire de création ; `dto()` retourne `TransactionDTO?` ou `None` si invalide |
| `KpiTile` | `QFrame` | Tuile KPI réutilisable ; `set_value(text)`, `set_tone(tone)` |

**Composition** : `TransactionsView` contient 5 `KpiTile`, possède un `TransactionTableModel`, ouvre `AddTransactionDialog`, utilise `FinanceController`.

### 3.8 Notes transverses

- `FinanceService` émet sur `EventBus` et utilise les constantes `Events` ; lève `ValidationError` et `NotFoundError`.
- `FinanceService` est **Python pur** : zéro import Qt ou SQLAlchemy direct (uniquement les repos).
- `FinanceController` instancie un nouveau `FinanceService` par appel (la session change à chaque fois).
- `TransactionsView` lit en synchrone via `list_transactions` mais reçoit ses **rafraîchissements** via signaux Qt (`transaction_created/deleted`, `kpis_refreshed`).

---

## 4. Diagramme d'activité détaillé

### 4.1 Source

Fichier : [docs/activity_diagram.puml](activity_diagram.puml) — contient **trois pages** (un flux par page).

### 4.2 Flux 1 — Créer une transaction

#### 4.2.1 Préconditions

- L'application est lancée, `TransactionsView` est affichée.
- Au moins un `Account` actif existe en base (sinon le combo est vide → la création échoue côté UI).

#### 4.2.2 Déroulement nominal

| # | Couloir (swimlane) | Action |
|---|---|---|
| 1 | Utilisateur | Clique `+ Nouvelle…` |
| 2 | TransactionsView | Ouvre `AddTransactionDialog` |
| 3 | AddTransactionDialog | Peuple les combos via `controller.list_accounts/list_categories/list_active_debts/list_active_goals` |
| 4 | Utilisateur | Remplit le formulaire, clique `Ajouter` |
| 5 | AddTransactionDialog | Vérifie les champs requis (label, compte, debt/goal si flow le requiert). Si KO → `Champ requis` + `stop` |
| 6 | AddTransactionDialog | Construit `TransactionDTO`, retourne `Accepted` |
| 7 | TransactionsView | Appelle `controller.create_transaction(dto)` |
| 8 | FinanceController | Ouvre `get_session()`, instancie `FinanceService(session)` |
| 9 | FinanceService | Exécute `_validate_transaction(dto)` |
| 10 | FinanceService | `tx_repo.add(Transaction)` |
| 11 | FinanceService | Si `flow_type == DEPENSE` **et** `category_id` → appelle `check_budget(...)`. Si `is_exceeded` → `bus.emit(BUDGET_EXCEEDED)` |
| 12 | FinanceService | `bus.emit(TRANSACTION_CREATED)` |
| 13 | FinanceController | Sortie du `with get_session()` ⇒ `session.commit()` automatique. Émet `transaction_created(tx)` |
| 14 | TransactionsView | `_on_transaction_created → _refresh()` ⇒ recharge KPIs + transactions |

#### 4.2.3 Branches d'erreur

- **Validation UI KO** : message `Champ requis` ⇒ `stop` (pas d'appel service).
- **Validation domaine KO** (`ValidationError`) : `FinanceController._run` attrape `LifeManagerError`, émet `error(message)`. `TransactionsView._on_error` affiche `QMessageBox.warning`. ⇒ `stop`.
- **Bug** : exception non-`LifeManagerError` → propagation (rollback automatique du `with get_session()`).

### 4.3 Flux 2 — Supprimer une transaction

#### 4.3.1 Préconditions

- Au moins une transaction existe pour le mois sélectionné.
- L'utilisateur a sélectionné une ligne dans le tableau (sinon `delete_button` est désactivé).

#### 4.3.2 Déroulement

| # | Couloir | Action |
|---|---|---|
| 1 | Utilisateur | Sélectionne une ligne |
| 2 | TransactionsView | `_on_selection_changed` ⇒ `delete_button.setEnabled(True)` |
| 3 | Utilisateur | Clique `Supprimer la transaction…` |
| 4 | TransactionsView | `QMessageBox.question(Yes/No)` |
| 5 | TransactionsView | Si `No` ⇒ `stop`. Si `Yes` ⇒ `controller.delete_transaction(tx.id)` |
| 6 | FinanceController | Ouvre `get_session()`, instancie `FinanceService` |
| 7 | FinanceService | `tx_repo.delete(tx.id)`. Si introuvable ⇒ `NotFoundError` (capté en aval) |
| 8 | FinanceService | `bus.emit(TRANSACTION_DELETED)` |
| 9 | FinanceController | `commit()` automatique. Émet `transaction_deleted(tx_id)` |
| 10 | TransactionsView | `_on_transaction_deleted → _refresh()` ⇒ recharge KPIs + transactions |

#### 4.3.3 Branche d'erreur

- `NotFoundError` ⇒ `error(message)` ⇒ `QMessageBox.warning` ⇒ `stop`.

### 4.4 Flux 3 — Naviguer / Changer de mois

#### 4.4.1 Déclencheurs

- Ouverture initiale de l'application.
- Sélection d'un mois dans `month_combo`.
- Tout `_refresh()` consécutif à un événement (`transaction_created`, `transaction_deleted`).

#### 4.4.2 Déroulement

| # | Couloir | Action |
|---|---|---|
| 1 | Utilisateur | Ouvre l'app ou choisit un mois |
| 2 | TransactionsView | `_refresh()`, lit le mois sélectionné |
| 3 | FinanceController | `get_monthly_kpis(month)` |
| 4 | FinanceService | `tx_repo.total_by_flow` × 4 (REVENU, DEPENSE, EPARGNE, DETTE), construit `MonthlyKPIs` |
| 5 | FinanceController | Émet `kpis_refreshed(kpis)` |
| 6 | TransactionsView | `_on_kpis_refreshed` ⇒ met à jour les 5 `KpiTile` (valeur + tonalité) |
| 7 | FinanceController | `list_transactions(month)` |
| 8 | FinanceService | `tx_repo.list_by_month_with_relations(m)` (joinedload account + category) |
| 9 | TransactionsView | `model.set_transactions(rows)`, désactive `delete_button` |

---

## 5. Règles métier transverses (rappel)

- **Net mensuel** = `Revenus − Dépenses − Épargne − Remboursements de dettes`. C'est le **cash disponible après allocations engagées**, pas le cashflow brut. Pour le cashflow brut, utiliser `TransactionRepository.cashflow(month)`.
- **`Transaction.signed_amount`** : positif si `sense=ENTREE`, négatif si `sense=SORTIE`. La direction est portée par `sense`, jamais par le signe d'un agrégat.
- **`Transaction.month`** : chaîne `YYYY-MM` utilisée pour tous les regroupements mensuels.
- **`Category` est transverse à `flow_type`** : n'importe quelle transaction peut porter une catégorie, et la catégorie reste optionnelle dans tous les cas. Les rapports « dépenses réelles » filtrent explicitement sur `flow_type=DEPENSE`.
- **Profondeur max d'arborescence catégorie = 2** (catégorie → sous-catégorie).
- **Plafonds budget** : un budget est défini **par (catégorie, mois)** ; pas de budget ⇒ aucune règle, donc pas de dépassement possible.

---

## 6. Hors champ v1 (rappel)

- Multi-utilisateur, authentification, gestion de rôles
- Synchronisation cloud, base distante
- Interface mobile / web
- Import automatique de relevés bancaires (planifié v2)
- API web (planifié v2)
- Modules Grocery, Nutrition, Dashboard, Settings (stubs présents, vides)
- Édition d'une transaction existante (planifié)
- Persistance complète des `Alert` (le dépassement actuel est uniquement signalé via `QMessageBox`)

---

## 7. Annexes

### 7.1 Index des diagrammes

| Diagramme | Fichier source | Format |
|---|---|---|
| Cas d'utilisation | [docs/use_case_diagram.puml](use_case_diagram.puml) | PlantUML |
| Classes | [docs/class_diagram.puml](class_diagram.puml) | PlantUML |
| Activité (3 flux) | [docs/activity_diagram.puml](activity_diagram.puml) | PlantUML — `newpage` par flux |

### 7.2 Rendu des diagrammes

Pour générer les images PNG/SVG depuis les sources PlantUML :

```bash
# Avec PlantUML installé
plantuml docs/use_case_diagram.puml
plantuml docs/class_diagram.puml
plantuml docs/activity_diagram.puml
```

### 7.3 Points d'entrée code (pour vérification)

| Élément | Fichier |
|---|---|
| Service métier finance | [lifemanager/finance/services/finance_service.py](../lifemanager/finance/services/finance_service.py) |
| Contrôleur finance | [lifemanager/finance/controllers/finance_controller.py](../lifemanager/finance/controllers/finance_controller.py) |
| Vue principale | [lifemanager/finance/views/transactions_view.py](../lifemanager/finance/views/transactions_view.py) |
| Dialogue d'ajout | [lifemanager/finance/views/add_transaction_dialog.py](../lifemanager/finance/views/add_transaction_dialog.py) |
| Modèles | [lifemanager/finance/models/](../lifemanager/finance/models/) |
| Repositories | [lifemanager/finance/repositories/](../lifemanager/finance/repositories/) |
| Bus d'événements | [lifemanager/core/events/bus.py](../lifemanager/core/events/bus.py) |
| Exceptions | [lifemanager/core/exceptions/exceptions.py](../lifemanager/core/exceptions/exceptions.py) |
| Repository de base | [lifemanager/core/repositories/base.py](../lifemanager/core/repositories/base.py) |
| Modèle de base | [lifemanager/core/models/base.py](../lifemanager/core/models/base.py) |
