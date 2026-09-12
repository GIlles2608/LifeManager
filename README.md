# LifeManager

Application desktop de gestion de vie personnelle — finances, courses, nutrition.

## Stack

- **Python 3.11+** + **PyQt6** (interface desktop)
- **SQLAlchemy 2.0** + **Alembic** (ORM + migrations)
- **PostgreSQL** (base de données locale)

## Mise en place

### 1. Prérequis

```bash
# Python 3.11+
python --version

# PostgreSQL local — créer la base
psql -U postgres -c "CREATE DATABASE lifemanager;"
```

### 2. Environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# ou : .venv\Scripts\activate    # Windows
```

### 3. Installation

```bash
pip install -e ".[dev]"
```

### 4. Configuration

```bash
cp .env.example .env
# Éditer .env avec vos credentials PostgreSQL
```

### 5. Migrations

```bash
# Créer la première migration (depuis les modèles)
alembic revision --autogenerate -m "initial schema"

# Appliquer
alembic upgrade head
```

### 6. Lancer l'application

```bash
python -m lifemanager
```

### 7. Tests

```bash
pytest
# ou avec coverage :
pytest --cov=lifemanager
```

## Structure

```
lifemanager/
├── core/               # Infrastrucure partagée
│   ├── config/         # Settings, DB session
│   ├── models/         # BaseModel (UUID, timestamps)
│   ├── events/         # Event bus (découplage modules)
│   └── exceptions/     # Hiérarchie d'exceptions
├── finance/            # Module finance
│   ├── models/         # Transaction, Account, Budget, Debt, Goal
│   ├── repositories/   # Accès DB (SQLAlchemy)
│   ├── services/       # Logique métier
│   ├── controllers/    # Pont View ↔ Service
│   └── views/          # Widgets PyQt6
├── grocery/            # Module courses (à compléter)
├── nutrition/          # Module nutrition (à compléter)
├── dashboard/          # Vue synthétique
└── settings/           # Préférences
migrations/             # Alembic migrations
tests/
├── unit/               # Tests sans DB
└── integration/        # Tests avec DB de test
```

## VSCode — extensions recommandées

- `ms-python.python` — support Python
- `ms-python.mypy-type-checker` — vérification de types
- `charliermarsh.ruff` — linting/formatting
- `mtxr.sqltools` + driver PostgreSQL — explorer la DB
- `bierner.markdown-mermaid` — prévisualiser les diagrammes ERD

## Commandes utiles

```bash
# Linting
ruff check lifemanager/

# Type checking
mypy lifemanager/

# Nouvelle migration après modification des modèles
alembic revision --autogenerate -m "description"
alembic upgrade head

# Rollback
alembic downgrade -1
```
