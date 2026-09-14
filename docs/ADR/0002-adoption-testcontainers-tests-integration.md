# 002 - Adoption de testcontainers-python pour les tests d'intégration

- **Statut** : Accepté
- **Date** : 2026-09-13

## Contexte

Le projet migre vers une architecture Port-Adaptateur (voir
[ADR-0001](0001-architecture-migration-hexagonal.md)), ce qui va
faire évoluer en profondeur les repositories (futurs adaptateurs) et
les entités du domaine. Ce refactoring touche directement la couche
de persistance et nécessite une suite de tests fiable pour valider
que le comportement observable (requêtes, agrégations, contraintes)
reste correct pendant la migration.

L'état actuel des tests, tel que documenté dans le `CLAUDE.md` du
projet, présente deux limites pour cet usage :

- Les tests unitaires mockent la session SQLAlchemy — ils ne
  couvrent donc pas les requêtes réellement exécutées contre
  PostgreSQL, notamment les agrégations SQL spécifiques au projet
  (`CASE WHEN sense = 'entree' …`, fonctions `to_char`, etc.) que
  `AccountRepository.get_balance` et
  `TransactionRepository.total_*`/`cashflow` utilisent.
- Les tests d'intégration nécessitent une base `lifemanager_test`
  déjà créée et accessible localement, dont le cycle de vie (création,
  état, nettoyage entre exécutions) n'est pas géré par la suite de
  tests elle-même. Rien ne garantit aujourd'hui que deux exécutions
  successives partent d'un état identique, et cette dépendance à un
  service externe préexistant rend la suite inutilisable telle
  quelle dans un pipeline CI/CD sans provisionnement manuel préalable.

Une façon fiable et reproductible de tester le comportement
spécifique à PostgreSQL est donc nécessaire avant d'engager le
refactoring vers l'architecture hexagonale.

## Decision

Le projet adopte `testcontainers-python` pour l'ensemble de sa suite
de tests d'intégration. Les tests unitaires ne sont pas concernés et
continuent de mocker la session SQLAlchemy, sans dépendance à une
base de données réelle.

- Une fixture pytest (scope `session`) démarre un container
  PostgreSQL éphémère au lancement de la suite, applique les
  migrations Alembic (`alembic upgrade head`), puis fournit une
  session SQLAlchemy connectée à ce container. Le container est
  détruit automatiquement en fin de suite, succès ou échec.
- **Isolation par rollback de transaction en défaut** : chaque test
  s'exécute dans une transaction ouverte en début de test et annulée
  (`rollback`) à la fin, sans commit — le schéma n'est chargé qu'une
  fois pour toute la suite. Pour les cas qui ne peuvent pas s'en
  satisfaire (code testé qui commite explicitement, contraintes
  inter-transactions), un **fallback par troncature**
  (`TRUNCATE ... RESTART IDENTITY CASCADE`) est disponible et
  documenté comme mécanisme d'exception, pas comme comportement par
  défaut.
- La base `lifemanager_test` gérée manuellement est retirée de
  l'usage courant : elle n'est plus nécessaire pour lancer les tests
  d'intégration, en local comme en CI.
- La migration des repositories vers cette suite se fait en deux
  vagues, par ordre de criticité et de complexité SQL :
  1. `TransactionRepository` — SQL le plus complexe (`func.to_char`
     pour le regroupement mensuel, agrégations `total_*`/`cashflow`).
  2. `AccountRepository` — `CASE WHEN` du calcul de solde
     (`get_balance`).
  3. `BudgetRepository` — logique métier critique (`check_budget`).
  4. Deuxième vague : `CategoryRepository`, `DebtRepository`,
     `SavingsGoalRepository`.

## Alternatives

- **Maintenir l'approche actuelle** (base `lifemanager_test` créée et
  gérée manuellement en local). Ne demande aucun changement, mais
  conserve les limites déjà identifiées en Contexte : cycle de vie
  non géré par la suite de tests, reproductibilité non garantie
  entre exécutions, et inutilisable telle quelle dans un pipeline
  CI/CD sans provisionnement manuel préalable de la base.

- **SQLite en mémoire pour les tests d'intégration.** Solution simple
  et rapide à mettre en place (pas de dépendance Docker), mais ne
  couvre pas le SQL spécifique à PostgreSQL que le projet utilise
  déjà (`func.to_char` pour le regroupement mensuel, `CASE WHEN` pour
  le calcul de solde) — ces requêtes échoueraient ou se comporteraient
  différemment sur SQLite, ce qui invaliderait l'objectif même de
  ces tests.

- **Docker Compose dédié aux tests** (`docker-compose.test.yml`,
  démarré manuellement ou via un script avant `pytest`). Fournit un
  vrai PostgreSQL comme testcontainers, mais laisse l'orchestration
  (démarrage, attente de disponibilité, arrêt, nettoyage) à la charge
  de scripts externes à la suite de tests elle-même — sans teardown
  automatique par exécution, et avec une intégration à un pipeline
  CI/CD plus manuelle qu'une fixture pytest auto-suffisante.


## Conséquences

- **Tests d'intégration fiables et reproductibles** : chaque
  exécution repart d'un schéma neuf via les migrations Alembic, ce
  qui élimine la dérive d'état entre exécutions et permet de détecter
  une migration Alembic cassée directement dans la suite de tests.

- **Suite exécutable en CI/CD sans provisionnement manuel** : Docker
  devient la seule dépendance d'environnement requise, ce qui ouvre
  la voie à l'intégration de ces tests dans un pipeline CI/CD sans
  étape préalable de création de base de données.

- **Nouvelle dépendance obligatoire : Docker** doit être disponible
  sur toute machine (poste de dev, agent CI) qui exécute la suite
  d'intégration — un environnement sans Docker (ou sans les
  permissions pour le lancer) ne peut plus faire tourner ces tests
  du tout, alors que l'ancienne approche ne demandait qu'un accès
  réseau à une base Postgres déjà démarrée.

- **Charge de discipline sur le choix rollback vs truncate** : chaque
  nouveau test d'intégration doit déterminer s'il peut se satisfaire
  de l'isolation par rollback (cas par défaut) ou s'il nécessite le
  fallback par troncature — un mauvais choix peut faire fuiter de
  l'état entre tests sans erreur immédiate, donc silencieusement.

- **Temps d'exécution local et CI à surveiller** : le démarrage du
  container PostgreSQL et l'application des migrations ajoutent un
  coût fixe au premier lancement de la suite (absent des tests
  unitaires mockés), à mesurer une fois les deux vagues de migration
  des repositories terminées.

- **Risque temporaire de double approche pendant la migration** :
  tant que les deux vagues ne sont pas achevées, certains
  repositories restent testés uniquement via mocks (aucune
  couverture du SQL réel) pendant que d'autres bénéficient déjà de
  testcontainers — écart de confiance à garder en tête tant que
  `CategoryRepository`, `DebtRepository` et `SavingsGoalRepository`
  n'ont pas basculé.