# 005 - Extraction des entités de domaine

- **Statut** : Accepté
- **Date** : 2026-09-17

## Contexte

L'[ADR-0001](0001-architecture-migration-hexagonal.md) pose la
migration vers l'architecture Port-Adaptateur,
l'[ADR-0003](0003-inversion-dependance-service.md) inverse la
dépendance côté écriture, et
l'[ADR-0004](0004-dtos-lecture-repo-vers-vue.md) introduit des DTOs
de lecture sur tout le chemin domaine → présentation. Ce découplage
progressif laisse cependant subsister un couplage plus profond,
jamais encore traité : la logique métier elle-même vit directement
sur les classes ORM.

Toutes les entités du domaine héritent de `BaseModel`
(`lifemanager/core/models/base.py:20`), lui-même une sous-classe
directe de `Base(DeclarativeBase)` — chaque entité métier est donc
structurellement une classe SQLAlchemy. Ce lien est renforcé par
`BaseRepository[T]`, dont le `TypeVar` est explicitement borné sur
`BaseModel` (`T = TypeVar("T", bound=BaseModel)`,
`lifemanager/core/repositories/base.py:18`) — un verrou structurel
qui empêche toute entité de domaine d'exister indépendamment de
SQLAlchemy tant que ce type générique reste inchangé.

Plusieurs règles métier concrètes vivent directement comme propriétés
sur ces classes ORM plutôt que dans le domaine pur :
`Transaction.signed_amount`, `Transaction.month`
(`lifemanager/finance/models/transaction.py`),
`Debt.repaid`, `Debt.progress`
(`lifemanager/finance/models/debt.py`), `SavingsGoal.remaining`,
`SavingsGoal.progress`
(`lifemanager/finance/models/savings_goal.py`). Il est
aujourd'hui impossible de tester cette logique métier sans démarrer
SQLAlchemy et charger une instance mappée, alors qu'elle ne dépend
d'aucune donnée externe à l'entité elle-même.

L'ADR-0004 rend ce refactoring sûr à entreprendre maintenant : la vue
ne dépend plus des entités ORM (elle lit des DTOs), donc modifier la
forme des entités de domaine ne risque plus de casser l'affichage.


## Décision

Les entités de domaine sont extraites des classes ORM : le domaine
gagne ses propres objets, indépendants de SQLAlchemy, et porte la
logique métier qui vivait jusqu'ici sur les modèles mappés.

- **Format des entités : `@dataclass(frozen=True)` par défaut**, avec
  des méthodes qui retournent de nouvelles instances plutôt que de
  muter l'état. Cohérent avec les DTOs de l'ADR-0004, force
  l'immutabilité, et suit le patron "value object". Par exemple,
  `Debt.record_payment(amount)` retourne un nouveau `Debt` avec
  `remaining` recalculé, plutôt que de modifier l'instance en place.

- **Les relations entre entités deviennent des UUID de référence**,
  pas des objets imbriqués : `Transaction.account_id: uuid.UUID`
  remplace `Transaction.account: Account`. Cohérent avec l'absence de
  cache d'identité du mapping (voir plus bas) — les DTOs de lecture
  de l'ADR-0004 restent la source des noms affichés côté vue, les
  entités de domaine n'ont pas besoin de porter le graphe d'objets
  complet.

- **Organisation du domaine** dans `finance/domain/` :

  ```
  finance/domain/
  ├── entities/
  ├── value_objects/           # peut rester vide pour l'instant
  ├── ports/                   # existe déjà depuis l'ADR-0003
  └── exceptions/               # exceptions métier (BudgetExceededError, etc.)
  ```

  Les exceptions métier, actuellement dans `core/`, sont déplacées
  vers `finance/domain/exceptions/` — elles sont spécifiques au
  domaine Finance, pas transverses à l'application. Ce déplacement
  règle au passage F14 (logique de formatage des montants en euros
  présente dans le noyau applicatif).

- **Les mappers vivent dans
  `finance/infrastructure/persistence/mappers/`**. Le package
  `infrastructure/` est créé dès cette étape, en parallèle du
  renommage des repositories déjà prévu :
  `finance/repositories/` devient
  `finance/infrastructure/persistence/repositories/`. Fait maintenant
  car le diff de cette étape est déjà dense — pas de bénéfice à
  séparer ce renommage dans une étape ultérieure.

- **Stratégie de mapping simple, sans cache d'identité** : chaque
  `_to_entity(orm_row)` crée une nouvelle instance. Deux lectures de
  la même ligne produisent deux objets `Transaction` distincts mais
  égaux (égalité structurelle via `@dataclass`). Pas de suivi
  d'identité entre lectures — YAGNI tant qu'aucun besoin concret ne
  l'exige.

- **`BaseRepository[T]` générique est supprimé** de
  `core/repositories/`, entièrement — pas seulement pour Finance.
  Chaque port est désormais typé explicitement sur son entité de
  domaine ; chaque adaptateur implémente son port sans hériter d'un
  CRUD générique borné sur `BaseModel`. Toute logique de CRUD
  partagée qui resterait réellement répétitive peut vivre comme
  fonction utilitaire, pas comme classe de base héritée. Ce patron
  (ports explicites, pas d'héritage CRUD générique) devient la règle
  pour tout futur module (Grocery, Nutrition inclus).

- **`FinanceService` reste à son emplacement actuel**, mais son
  constructeur change : il reçoit des ports typés sur les entités de
  domaine, plus sur les modèles ORM. Sa logique interne migre
  progressivement vers les entités elles-mêmes — par exemple,
  `signed_amount` disparaît du service une fois qu'il devient une
  méthode de l'entité `Transaction`.

## Critères de succès

Cette étape est considérée terminée lorsque les critères suivants
sont tous vérifiés :

- [ ] Aucun import `sqlalchemy` dans `finance/domain/`.
- [ ] Aucun import `PyQt6` dans `finance/domain/`.
- [ ] Les tests unitaires des entités de domaine s'exécutent sans
      démarrer PostgreSQL ni SQLAlchemy.
- [ ] `Transaction.signed_amount`, `Transaction.month`,
      `Debt.repaid`, `Debt.progress`, `SavingsGoal.remaining`,
      `SavingsGoal.progress` vivent sur les entités de domaine, plus
      sur les modèles ORM.
- [ ] Les modèles ORM (`finance/models/`, renommé ou non) sont
      strictement anémiques : uniquement colonnes et relations
      SQLAlchemy, aucune `@property` métier restante.
- [ ] Les mappers entité ↔ ORM sont testés par des tests unitaires
      dédiés, indépendants des tests d'entité et de repository.
- [ ] Les tests d'intégration existants
      ([ADR-0002](0002-adoption-testcontainers-tests-integration.md))
      passent toujours.
- [ ] Les tests unitaires de `FinanceService` passent toujours,
      adaptés aux nouveaux ports typés sur les entités de domaine.
- [ ] Aucune nouvelle migration Alembic générée — le schéma physique
      ne change pas, seule l'organisation du code applicatif évolue.


## Alternatives

- **Entités mutables.** Rejeté : plus de surface pour des bugs
  d'état partagé (une référence modifiée en place peut être vue
  différemment par deux consommateurs) pour un gain de simplicité
  marginal — les méthodes qui retournent une nouvelle instance
  restent simples à écrire et à raisonner.

- **SQLAlchemy Imperative Mapping au lieu de mappers manuels.**
  Alternative valide qui garde le mapping proche de l'ORM tout en
  séparant la classe entité de la classe mappée. Rejeté : reste un
  couplage à SQLAlchemy (les entités doivent respecter certaines
  contraintes du mapper impératif) et masque le mécanisme de
  conversion plutôt que de le rendre explicite — moins pédagogique
  dans le cadre d'apprentissage de ce projet (voir
  [ADR-0001](0001-architecture-migration-hexagonal.md)).

- **Pydantic pour les entités de domaine.** Rejeté : sur-ingénierie
  (pas de validation externe à faire, les données sont déjà validées
  en base et par les DTOs d'entrée) et source de confusion entre
  DTO et entité de domaine — deux objets aux responsabilités
  différentes qui finiraient par se ressembler.

- **Reporter cette étape, ne traiter que les mappers pour l'instant.**
  Rejeté : la fuite qui bloque tout le reste (logique métier
  attachée aux classes ORM, `BaseRepository[T]` borné sur
  `BaseModel`) est la cause racine — introduire des mappers sans
  extraire les entités ne résout rien, puisqu'il n'y aurait encore
  rien de découplé à mapper vers.

## Conséquences

- **Coût le plus élevé de la roadmap, en volume et en risque** :
  touche les 6 entités, leurs 6 mappers, leurs 6 adaptateurs, les
  ports et le service — la surface de changement la plus large parmi
  tous les ADR actés à ce jour.

- **Le domaine devient enfin testable en isolation** : c'est le
  geste qui matérialise concrètement l'architecture hexagonale posée
  en ADR-0001 — la logique métier peut être testée sans démarrer
  SQLAlchemy ni PostgreSQL.

- **Chaque entité gagne son propre fichier de tests unitaires**,
  couvrant ses règles métier isolément et sans dépendance à une base
  de données — effet secondaire positif direct de l'extraction.

- **Duplication apparente entre entités de domaine et modèles ORM**
  (mêmes champs représentés deux fois, sous deux formes). Structurelle,
  pas un défaut : c'est le prix du découplage entre la représentation
  métier et la représentation persistée, assumé comme tel plutôt que
  comme dette à résorber.

- **`FinanceService` garde temporairement une logique de
  conversion** entre ports et entités pendant cette étape — sera
  nettoyé à une étape ultérieure, une fois que la logique métier
  aura fini de migrer entièrement vers les entités elles-mêmes.

