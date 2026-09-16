# 004 DTOs de lecture sur tout le chemin

- **Statut** : Accepté
- **Date** : 2026-09-16
 

## Contexte

L'[ADR-0001](0001-architecture-migration-hexagonal.md) pose la
migration vers l'architecture Port-Adaptateur,
l'[ADR-0002](0002-adoption-testcontainers-tests-integration.md)
fournit le filet de tests d'intégration, et
l'[ADR-0003](0003-inversion-dependance-service.md) inverse la
dépendance côté écriture : `FinanceService` ne dépend plus de
`Session` ni des repositories concrets. Le chemin d'écriture est
désormais découplé de l'infrastructure ; le chemin de lecture, lui,
ne l'est pas encore.

Aujourd'hui, le chemin de lecture traverse toutes les couches sans
aucune traduction : `FinanceService.list_transactions` et
`FinanceController.list_transactions` retournent tous deux
`list[Transaction]`
(`lifemanager/finance/services/finance_service.py:131`,
`lifemanager/finance/controllers/finance_controller.py:81`) — les
entités SQLAlchemy elles-mêmes remontent jusqu'à la vue.
`TransactionTableModel`, côté présentation, lit directement
`tx.account.name` et `tx.category.name`
(`lifemanager/finance/views/transaction_table_model.py:70,72`) sur
ces entités.

Ce couplage transparent est actuellement rendu possible par deux
béquilles techniques, présentes dans le code explicitement pour le
supporter :

- `TransactionRepository.list_by_month_with_relations` charge les
  relations `account` et `category` par `joinedload`
  (`lifemanager/finance/repositories/transaction_repo.py:45-46`),
  avec un commentaire en dur qui documente pourquoi : *"the caller
  will read tx.account.name / tx.category.name for every row"*.
- `expire_on_commit=False` est configuré sur la session
  (`lifemanager/core/config/database.py:37`, commentaire *"avoid
  lazy-load issues after commit"*) pour que ces entités restent
  lisibles après la fermeture de la transaction qui les a chargées —
  sans quoi accéder à `tx.account.name` depuis la vue lèverait une
  erreur de session détachée.

Ces deux mécanismes existent uniquement pour compenser l'absence de
traduction entre le domaine et la présentation sur le chemin de
lecture. Un DTO d'écriture (`TransactionDTO`,
`finance_service.py:39`) existe déjà et remplit ce rôle dans l'autre
sens (présentation → domaine) : les DTOs de lecture (domaine →
présentation) sont la symétrie manquante.


## Décision

Toute lecture qui traverse la frontière domaine → présentation
retourne un DTO, jamais une entité ORM. Ce principe s'applique dès
cette étape à l'ensemble des entités du module Finance exposées à
une vue : `Transaction`, `Account`, `Category`, `Budget`, `Debt`,
`SavingsGoal`.

- **Format des DTOs : dataclasses gelées** (`@dataclass(frozen=True)`).
  Simple, standard, immutable, sans dépendance nouvelle.
- **Les DTOs de lecture vivent dans `finance/application/dto/`**, à
  côté des DTOs d'écriture existants (`TransactionDTO`).
- **Un DTO générique par entité**, par exemple `TransactionReadDTO`,
  `AccountReadDTO`, `CategoryReadDTO`, `BudgetReadDTO`, `DebtReadDTO`,
  `SavingsGoalReadDTO` — chacun contient tout ce qu'un widget pourrait
  avoir besoin de lire pour cette entité, y compris les champs
  aujourd'hui obtenus via relation ORM (ex.
  `TransactionReadDTO.account_name`, `TransactionReadDTO.category_name`
  remplacent `tx.account.name`, `tx.category.name`).
- **La conversion entité ORM → DTO se fait dans le repository
  (adaptateur) correspondant.** Le repository devient responsable de
  *ce qu'il expose*, pas seulement de *ce qu'il charge*. Cohérent
  avec l'inversion de dépendance de l'ADR-0003 : le port déclare un
  retour de type DTO, l'adaptateur SQLAlchemy est seul responsable de
  savoir le construire à partir des entités et relations chargées.
- **Les ports et signatures de retour changent en conséquence sur
  toute la chaîne** : chaque méthode de port qui retournait
  `list[Transaction]` (ou une autre entité) retourne désormais
  `list[TransactionReadDTO]` (ou le DTO correspondant) —
  `TransactionRepositoryPort.list_by_month_with_relations`,
  `FinanceService.list_transactions`,
  `FinanceController.list_transactions` sont mis à jour en cascade.
  Les entités ORM ne remontent plus au-dessus de la couche
  repository/adaptateur.
- **Le signal Qt `transaction_created`**, qui transporte aujourd'hui
  une entité ORM, devient `pyqtSignal(TransactionReadDTO)`. Le
  contrôleur effectue la conversion avant l'émission du signal.

## Critères de succès

Cette étape est considérée terminée lorsque les critères suivants
sont tous vérifiés :

- [ ] Aucun import de modèle ORM (`from finance.models import
      Transaction`, ou équivalent pour les autres entités) dans le
      package `finance/views/` ni dans `finance_controller.py`.
- [ ] Les signatures publiques du contrôleur retournent des DTOs,
      jamais des entités ORM.
- [ ] Les signaux Qt transportent des DTOs (`transaction_created`
      émet `TransactionReadDTO`).
- [ ] `joinedload` retiré de `transaction_repo.py` — les DTOs
      contiennent déjà les champs plats nécessaires, le chargement
      des relations pour un accès différé n'est plus utile.
- [ ] `expire_on_commit=False` retiré de `database.py` — plus
      nécessaire une fois qu'aucune entité ORM ne circule au-delà du
      repository qui l'a chargée.
- [ ] Tests `pytest-qt` ajoutés sur `TransactionTableModel`
      (couverture actuelle 0 %) avant le refactor, pour garantir la
      non-régression du comportement observable de la vue.
- [ ] Tests unitaires et d'intégration existants passent toujours.
- [ ] Aucune nouvelle migration Alembic générée — ce changement ne
      touche que la couche applicative, pas le schéma.

## Alternatives

- **Pydantic au lieu de dataclasses.** Rejeté : sur-ingénierie pour
  ce cas — pas de validation externe à faire sur des données déjà
  validées en base, pas de sérialisation JSON en jeu ici. Les
  dataclasses gelées suffisent et n'ajoutent aucune dépendance.

- **Conversion faite dans le service plutôt que dans le
  repository.** Rejeté : le service devrait recevoir des DTOs déjà
  construits et raisonner dessus, pas assumer la responsabilité de
  convertir des entités ORM — ce qui le recouplerait indirectement à
  la forme des entités SQLAlchemy, à l'opposé de l'ADR-0003.

- **Ne rien introduire, laisser les entités ORM circuler jusqu'à la
  vue.** Rejeté : contredit directement l'ADR-0001 (frontière
  domaine/présentation), et bloque la suite de la roadmap qui suppose
  un chemin de lecture découplé.

- **DTOs multiples par cas d'usage dès maintenant** (ex. un DTO
  allégé pour la liste, un DTO détaillé pour l'édition). Reporté :
  YAGNI — un DTO générique par entité suffit tant qu'aucun besoin
  concret de vue allégée n'est observé ; à reconsidérer si un écran
  spécifique impose un sous-ensemble de champs pour des raisons de
  performance ou de lisibilité.

## Conséquences

- **Coût de mise en œuvre le plus élevé de la roadmap jusqu'ici** :
  touche 5 fichiers de production par entité migrée (repository,
  service, contrôleur, table model, vue), plus les tests associés —
  la plus grosse étape en volume de code parmi les ADR déjà actés.

- **La vue devient indépendante de l'ORM** : `TransactionTableModel`
  et les autres widgets lisent des DTOs immuables, jamais des
  entités SQLAlchemy — un changement de schéma ou de nom de relation
  côté ORM n'impacte plus directement la présentation tant que le
  DTO reste stable.

- **Suppression des deux béquilles identifiées en Contexte** :
  `joinedload` (transaction_repo.py) et `expire_on_commit=False`
  (database.py) deviennent inutiles et sont retirés — plus aucune
  entité ORM ne survit au-delà de la transaction qui l'a chargée,
  donc plus besoin de la garder lisible après coup.

- **Duplication apparente entre entités ORM et DTOs**, chaque champ
  du DTO reflétant un champ ou une relation de l'entité
  correspondante. Acceptée comme temporaire : à une étape future non
  encore numérotée, les entités ORM sont amenées à devenir plus
  anémiques (moins de logique et de relations exposées côté domaine),
  ce qui changera la nature de cette duplication plutôt que de
  l'éliminer d'un coup ici.