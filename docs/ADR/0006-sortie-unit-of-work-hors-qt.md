# 0006 - Sortie du Unit of Work hors de Qt

- **Statut** : Accepté
- **Date** : 2026-09-22

## Contexte

L'[ADR-0005](0005-extraction-entites-domaine.md) a formalisé les
ports de persistance côté domaine et introduit la séparation
`domain/` / `application/` / `infrastructure/` au sein du module
Finance. Un point reste non traité : l'orchestration transactionnelle
elle-même n'a pas de port dédié — elle vit implicitement dans
`FinanceController._run()`.

Aujourd'hui, `FinanceController._run()`
(`lifemanager/finance/controllers/finance_controller.py:131`) ouvre
une session via `get_session()`, construit `FinanceService` par
`build_finance_service(session)`, exécute l'opération demandée, puis
laisse le context manager de la session commiter en sortie de bloc
ou rollback sur exception (documenté dans le code comme "Pattern B
Unit-of-Work"). C'est le seul point de composition de l'application :
session, construction du service, et gestion d'erreur Qt (capture de
`LifeManagerError`/`FinanceDomainError`, émission du signal `error`)
y sont mélangés, à l'intérieur d'une classe `QObject` — donc dans la
couche présentation, qui ne devrait pas porter cette responsabilité
selon l'architecture posée en ADR-0001.

Il n'existe aujourd'hui aucun port qui nomme et abstrait ce concept
d'unité de travail (Unit of Work). L'orchestration transactionnelle
n'est ni un besoin du domaine (les entités n'ont pas besoin de savoir
qu'une transaction existe) ni un détail d'infrastructure pur (elle
doit rester pilotable depuis la couche applicative) — elle manque
comme port sortant orchestrateur explicite entre les deux.


## Décision

L'orchestration transactionnelle est extraite dans un port explicite
`AbstractUnitOfWork`, sorti de `FinanceController` : le contrôleur ne
construit plus `get_session()` lui-même.

- **Le port `AbstractUnitOfWork` est défini dans
  `finance/application/ports/unit_of_work.py`.** Le Unit of Work
  n'est pas une règle métier — le domaine n'a pas besoin de savoir
  qu'une transaction existe pour rester vrai — c'est un contrat
  d'orchestration qui appartient à la couche application. Cohérent
  avec la séparation domain/application/infrastructure posée en
  ADR-0005.

- **L'implémentation SQLAlchemy vit dans
  `finance/infrastructure/persistence/unit_of_work.py`**
  (`SqlAlchemyUnitOfWork`), aux côtés des mappers et des repositories
  déjà présents dans `infrastructure/persistence/`. Structure
  complète du module :

  ```
  finance/
  ├── application/
  │   ├── dto/
  │   ├── ports/
  │   │   └── unit_of_work.py     # AbstractUnitOfWork
  │   ├── services/                # FinanceService (transitoire)
  │   └── use_cases/               # peut rester vide pour l'instant
  ├── domain/
  │   ├── entities/
  │   ├── ports/                   # ports de repositories
  │   └── exceptions/
  └── infrastructure/
      └── persistence/
          ├── mappers/
          ├── repositories/
          └── unit_of_work.py     # SqlAlchemyUnitOfWork
  ```

- **`FinanceService` est conservé et relocalisé dans
  `finance/application/services/`**, plutôt que remplacé par un
  use-case par méthode publique (`CreateTransactionUseCase`,
  `CheckBudgetUseCase`, `GetMonthlyKPIsUseCase`, etc.). Son
  constructeur change pour consommer l'`AbstractUnitOfWork` plutôt
  que des ports de repository injectés séparément — le service
  devient une façade applicative qui délègue au UoW pour orchestrer
  la transaction. Les `use_cases/` explicites restent un dossier
  vide pour l'instant, ouvert pour une introduction ultérieure si le
  service grossit au point de le justifier.

- **Le Unit of Work est un port d'orchestration applicative,
  distinct des ports de repository.** Il vit dans
  `finance/application/ports/`, tandis que les ports de repository
  introduits en ADR-0003/0005 restent dans `finance/domain/ports/` —
  cohérent avec la variante DDD-friendly retenue à cette étape : les
  repositories font partie du langage du domaine (ils exposent des
  entités), le Unit of Work appartient à l'orchestration applicative
  (il coordonne une transaction autour de plusieurs repositories).

- **`FinanceController` devient un pur pont entre Qt et la couche
  applicative.** Il reçoit un service applicatif à son constructeur,
  appelle ses méthodes, et convertit les résultats en signaux Qt.
  Aucune ouverture de session, aucune manipulation transactionnelle
  ne subsiste dans le contrôleur — il ne connaît plus `Session` ni
  `get_session()`. Le Unit of Work est injecté au constructeur sous
  forme de factory, pattern décrit par **Percival & Gregory**
  (*Architecture Patterns with Python*). `_run()` ne disparaît pas
  mais se réduit à un wrapper minimal — appeler `op(uow)` et traduire
  les exceptions domaine (`LifeManagerError`/`FinanceDomainError`) en
  signal `error` — plutôt que de dupliquer ce bloc try/except dans
  chacune des méthodes publiques du contrôleur.

- **La composition root remonte hors de `__main__.py`.**
  Aujourd'hui, `__main__.py` assume la composition de l'application.
  Elle est déplacée vers `lifemanager/bootstrap.py`, à la racine du
  projet, qui appelle les fonctions `build_*` de chaque module (par
  exemple `finance.infrastructure.bootstrap.build_finance_service`)
  pour assembler l'application complète. `__main__.py` devient une
  coquille minimale :

  ```python
  app = build_application()
  app.run()
  ```

  Ce découplage prépare l'ajout des futurs modules (`grocery/`,
  `nutrition/`) sans avoir à réécrire la composition à chaque fois —
  chaque module expose son propre point d'assemblage, et
  `bootstrap.py` les compose au niveau racine.



## Critères de succès

Cette étape est considérée terminée lorsque les critères suivants
sont tous vérifiés :

- [ ] Aucun import `sqlalchemy` dans `finance/application/`.
- [ ] Aucun `get_session()` ni gestion de transaction dans
      `finance/controllers/`.
- [ ] Les tests unitaires de `FinanceService` utilisent un
      `FakeUnitOfWork` en mémoire, plus aucun mock direct de session
      ou de repository SQLAlchemy.
- [ ] `lifemanager/bootstrap.py` existe et centralise la composition
      de l'application.
- [ ] `__main__.py` réduit à quelques lignes (parsing des arguments,
      appel à `bootstrap`, lancement de l'application).
- [ ] Les tests d'intégration
      ([ADR-0002](0002-adoption-testcontainers-tests-integration.md))
      passent toujours.
- [ ] Aucune nouvelle migration Alembic générée — ce changement ne
      touche que l'organisation du code applicatif, pas le schéma.

## Alternatives

- **Garder le Unit of Work dans le contrôleur, injecter uniquement la
  session au service.** Rejeté : ne résout pas la fuite sur le fond
  — le contrôleur Qt continuerait à porter la responsabilité de
  l'orchestration transactionnelle, ce que cet ADR cherche
  précisément à faire sortir de la couche présentation.

- **`FinanceService` reçoit l'`AbstractUnitOfWork` en paramètre de
  chaque méthode plutôt qu'à son constructeur.** Rejeté : disperse la
  dépendance au UoW dans chaque signature de méthode publique plutôt
  que de la centraliser une fois à la construction — plus verbeux
  pour chaque appelant, sans bénéfice correspondant.

- **Un use-case explicite par méthode publique du service**
  (`CreateTransactionUseCase`, `CheckBudgetUseCase`,
  `GetMonthlyKPIsUseCase`, etc.), avec disparition de
  `FinanceService`. Reporté : sur-ingénierie sans besoin actuel — le
  service compte 8 à 10 méthodes, ce qui ferait 8 à 10 nouveaux
  fichiers pour un gain de lisibilité marginal. Reste une option
  ouverte si le service devient trop gros pour rester une façade
  unique lisible.

- **Unit of Work ambiant, exposé via une context variable** plutôt
  qu'injecté explicitement. Rejeté : introduit une forme de magie
  implicite (la transaction courante devient un état global caché)
  et complique les tests, qui devraient alors manipuler cet état
  ambiant plutôt que de simplement injecter un `FakeUnitOfWork`.

- **`with unit_of_work` ouvert dans le contrôleur** plutôt que dans
  le service applicatif. Rejeté : la frontière transactionnelle
  appartient à la couche application, pas à l'interface utilisateur
  — cohérent avec le rôle de pur pont assigné au contrôleur en
  Décision.

## Conséquences

- **Coût moyen à important** : touche le service applicatif, les 6
  repositories (interface au UoW), le contrôleur, `__main__.py`.

- **Le contrôleur Qt devient trivial et testable** : réduit à un pur
  pont entre signaux Qt et appels au service applicatif, sans logique
  transactionnelle à mocker pour le tester.

- **Le service applicatif devient portable vers d'autres interfaces**
  (CLI, web) sans modification : il ne dépend plus de Qt ni
  indirectement de la façon dont une session est ouverte, seulement
  du port `AbstractUnitOfWork`.

- **Tests unitaires du service enfin propres** : un `FakeUnitOfWork`
  en mémoire remplace l'ensemble des mocks de repositories
  individuels utilisés jusqu'ici.

- **Point d'attention : durée de vie du Unit of Work.** Le UoW garde
  en mémoire l'ensemble de ses repositories pendant toute sa durée de
  vie — à ne pas réutiliser tel quel pour des opérations très longues
  (streaming, traitements par lot massifs) sans réévaluer ce choix.