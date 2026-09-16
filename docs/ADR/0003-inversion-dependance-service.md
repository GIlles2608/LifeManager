# 003-Inversion de dépendance du service

- **Statut** : Accepté
- **Date** : 2026-09-15

## Contexte

L'[ADR-0001](0001-architecture-migration-hexagonal.md) acte la
migration vers une architecture Port-Adaptateur, et
l'[ADR-0002](0002-adoption-testcontainers-tests-integration.md)
fournit le filet de tests d'intégration nécessaire pour refactorer la
couche de persistance en confiance. Cette étape s'attaque à la
première application concrète du pattern sur le domaine : le
découplage de `FinanceService` vis-à-vis de SQLAlchemy.

`FinanceService` (`lifemanager/finance/services/finance_service.py`)
présente aujourd'hui deux fuites d'infrastructure dans le domaine,
documentées dans l'audit de refactoring :

- **F3 — le service est typé sur `Session`.**
  `FinanceService.__init__(self, session: Session)` importe
  `sqlalchemy.orm.Session` en tête de fichier et impose ce type
  concret au constructeur. Le domaine dépend directement d'un détail
  d'infrastructure alors qu'il ne devrait dépendre que d'une
  abstraction.
- **F4 — les repositories sont instanciés en dur.** Le constructeur
  construit lui-même ses 6 dépendances
  (`TransactionRepository(session)`, `BudgetRepository(session)`,
  `CategoryRepository(session)`, `DebtRepository(session)`,
  `AccountRepository(session)`, `SavingsGoalRepository(session)`),
  sans possibilité d'injection. Aucune substitution n'est possible
  sans modifier le code du service lui-même.

La conséquence la plus visible de ces deux fuites est déjà présente
dans la suite de tests actuelle : pour isoler `FinanceService` en
test unitaire, les tests réécrivent directement des attributs privés
du service (`svc._tx_repo = MagicMock()`), ce qui viole
l'encapsulation plutôt que de passer par le constructeur — signe que
la frontière d'injection qui devrait exister n'existe pas encore.

Cette étape est volontairement circonscrite à une seule sous-couche
du domaine (`FinanceService` et sa frontière avec les repositories),
plutôt qu'à l'ensemble de la migration hexagonale : c'est le
changement au rapport effet/coût le plus favorable de la roadmap,
et une base concrète pour juger si l'approche se généralise bien
avant de l'appliquer aux autres services.


## Décision

`FinanceService` ne dépend plus de `Session` ni des classes
repository concrètes. Il dépend uniquement de ports définis côté
domaine, injectés par son constructeur.

- **Un `BaseRepositoryPort[T]` générique**, `Protocol` miroir de
  `BaseRepository[T]` (`add`, `delete`, `get_by_id`, `find_by_id`,
  `list_all`), défini dans `finance/domain/ports/`.
- **Un port par repository existant**, chacun étendant
  `BaseRepositoryPort[T]` et ajoutant uniquement ses méthodes propres
  déjà utilisées par `FinanceService` : `TransactionRepositoryPort`,
  `BudgetRepositoryPort`, `CategoryRepositoryPort`,
  `DebtRepositoryPort`, `AccountRepositoryPort`,
  `SavingsGoalRepositoryPort` — tous dans `finance/domain/ports/`.
- **`FinanceService.__init__` prend les 6 ports en paramètres
  nommés** (ex. `tx_repo: TransactionRepositoryPort`, `budget_repo:
  BudgetRepositoryPort`, …) au lieu d'une `Session` — le domaine
  n'importe plus `sqlalchemy.orm.Session`.
- **Les classes repository SQLAlchemy actuelles restent en place**
  dans `finance/repositories/`, sans renommage ni déplacement ;
  elles deviennent des adaptateurs de fait en satisfaisant la forme
  structurelle du `Protocol` correspondant, sans modification de
  leur code.
- **Une factory manuelle** (`build_finance_service(session: Session)
  -> FinanceService`) reste le seul point du code qui connaît à la
  fois `Session` et les classes repository concrètes : elle
  instancie les 6 repositories à partir de la session, puis les
  injecte dans `FinanceService`. C'est le point de composition
  explicite de l'inversion de dépendance.
- Le code appelant (contrôleurs, tests d'intégration) construit
  désormais le service via cette factory plutôt que via
  `FinanceService(session)` directement.

## Critères de validation

Cette étape est considérée terminée lorsque les critères suivants
sont tous vérifiés :

- [ ] Aucun `import` lié à SQLAlchemy (`sqlalchemy.orm.Session` ou
      autre) ne subsiste dans `finance_service.py`.
- [ ] Le constructeur de `FinanceService` prend les 6 ports en
      paramètres injectés ; il ne prend plus de `Session` en
      paramètre.
- [ ] Les 22 tests unitaires existants de `FinanceService` passent
      en construisant le service via son constructeur (ports mockés
      injectés), sans monkeypatcher d'attributs privés après
      construction (`svc._tx_repo = MagicMock()` disparaît du code
      de test).
- [ ] Les tests d'intégration mis en place par
      [ADR-0002](0002-adoption-testcontainers-tests-integration.md)
      continuent de passer sans modification de leur logique métier
      testée.
- [ ] Une fonction factory `build_finance_service(session: Session)
      -> FinanceService` existe (dans `bootstrap.py` ou équivalent)
      et est le seul point du code appelant qui connaît à la fois
      `Session` et les classes repository concrètes.

## Alternatives

- **`ABC` au lieu de `Protocol` pour définir les ports.** Rejeté :
  plus verbeux (chaque adaptateur doit hériter explicitement de la
  classe abstraite), moins idiomatique en Python moderne pour ce
  cas d'usage, et force un lien d'héritage entre les repositories
  SQLAlchemy existants et une classe abstraite — alors que
  `Protocol` permet aux classes repository actuelles de rester
  inchangées et de satisfaire le port par leur seule forme
  structurelle (duck typing statique).

- **Injecter uniquement la `Session`, garder les repositories instanciés à l'intérieur du service.** Rejeté : supprime la
  construction en dur des repositories (F4), mais laisse le service
  typé sur `Session` (F3) et dépendant de SQLAlchemy de façon
  transitive — ne règle qu'une des deux fuites identifiées en
  Contexte et ne fait pas apparaître de frontière de port testable.

- **Introduire un framework d'injection de dépendances
  (`dependency-injector`) dès cette étape.** Reporté : sur-ingénierie
  au stade actuel — une factory manuelle suffit pour un seul service
  avec six dépendances, et le périmètre volontairement étroit de
  cette étape (voir Contexte) ne justifie pas d'introduire un
  framework supplémentaire. Peut être reconsidéré si le nombre de
  services et de dépendances croît significativement.

- **Ne rien faire, continuer avec les mocks internes actuels**
  (réécriture d'attributs privés dans les tests). Rejeté : contredit
  directement la décision prise en
  [ADR-0001](0001-architecture-migration-hexagonal.md) d'adopter une
  architecture Port-Adaptateur, et laisse `FinanceService` sans
  frontière d'injection explicite — les deux fuites F3 et F4
  persistent.


## Conséquences

- **Coût de mise en œuvre faible** : un seul fichier de production
  modifié (`finance_service.py` + nouveau module
  `finance/domain/ports/`), une fixture de test à réécrire pour
  construire le service via la factory plutôt que directement.

- **Preuve concrète que le pattern hexagonal fonctionne sur le code
  réel du projet**, avant de généraliser l'approche aux autres
  services et modules (Grocery, Nutrition) — valide l'ADR-0001 sur
  un cas réel plutôt que sur le principe seul.

- **Tests unitaires plus propres** : `FinanceService` devient
  constructible directement avec des `MagicMock()` respectant les
  ports, injectés par le constructeur — la pratique actuelle
  (`svc._tx_repo = MagicMock()`, réécriture d'attributs privés après
  construction) disparaît.

- **Frontière du port sortant rendue visible** : les six
  dépendances de `FinanceService` sont désormais explicites dans sa
  signature plutôt qu'implicites dans son corps — quiconque lit le
  constructeur voit immédiatement de quoi le service a besoin.

- **Nombre de paramètres du constructeur en hausse (6 ports
  nommés)** : acceptable au regard du nombre de repositories actuels,
  mais à surveiller si `FinanceService` continue de croître — un
  service qui dépasserait significativement 6 à 8 dépendances
  directes serait un signal pour reconsidérer soit le découpage du
  service, soit l'introduction d'un framework d'injection de
  dépendances (cf. alternative reportée ci-dessus).