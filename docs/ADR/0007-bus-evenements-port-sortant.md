# 007 - Bus d'événements comme port sortant

- **Statut** : Accepté
- **Date** : 2026-09-29

## Contexte

`core/events/bus.py` expose un singleton `bus` global (instance
d'`EventBus`), importé directement par
`finance/application/services/finance_service.py:9`
(`from lifemanager.core.events.bus import Events, bus`). Le service
émet aujourd'hui quatre événements :
`Events.TRANSACTION_CREATED`, `Events.TRANSACTION_DELETED`,
`Events.BUDGET_EXCEEDED`, `Events.DEBT_UPDATED`
(`finance_service.py:89,90,97,155`). D'autres constantes existent
déjà dans `Events` pour des événements pas encore émis
(`GOAL_UPDATED`, et les futurs événements Grocery/Nutrition/App
lifecycle).

Aucun abonné n'est enregistré dans le code applicatif actuel : le bus
fonctionne aujourd'hui en émetteur seul (*emitter-only*) — les
événements sont publiés mais rien ne les consomme encore.

Le singleton `bus` est créé à l'import du module
(`bus = EventBus()`, `core/events/bus.py:42`) et n'est pas
substituable sans patch en test : `FinanceService` dépend de lui de
façon cachée, une dépendance qui ne figure nulle part dans sa
signature ni dans son constructeur.

C'est une incohérence avec le reste de l'architecture actuelle : tous
les autres ports sortants du service sont désormais injectés — les
repositories via le Unit of Work
([ADR-0006](0006-sortie-unit-of-work-hors-qt.md)), les mappers via la
couche infrastructure ([ADR-0005](0005-extraction-entites-domaine.md)).
Le bus d'événements est le dernier holdout, le seul point où le
service touche encore une dépendance globale non injectée.

## Décision

Le bus d'événements devient un port sortant explicite, injecté, et
la publication passe par un pattern transactional outbox porté par
le Unit of Work — un événement n'est jamais publié pour un état qui
n'a finalement pas été validé en base.

- **`AbstractEventPublisher` est défini dans
  `core/ports/event_publisher.py`.** Contrairement au Unit of Work
  (spécifique à Finance, car les types de repositories métier
  diffèrent par module), le contrat de publication d'événements est
  générique : `publish(event: DomainEvent)`. Aucune
  raison de le dupliquer par module — ce port vit dans `core/` et
  prépare l'ajout futur des modules Grocery et Nutrition.

- **Format des événements : `@dataclass(frozen=True)` par type
  d'événement.** Cohérent avec les entités (ADR-0005) et les DTOs
  (ADR-0004). Le typage est plus fort qu'un `dict` générique, un
  abonné peut faire du pattern matching sur le type reçu. Coût
  mineur (5-6 dataclasses courtes) ; les événements deviennent une
  partie explicite du contrat métier plutôt qu'une convention
  informelle de noms de chaînes et de payloads implicites.

- **Les définitions d'événements vivent dans le domaine du module
  correspondant** : `finance/domain/events/`. Un événement métier
  ("une transaction a été créée") est un fait du domaine, pas un
  détail d'orchestration — le service applicatif se contente de le
  publier, il ne le définit pas. Cohérent avec l'approche DDD déjà
  retenue en ADR-0005.

- **Chaque entité de domaine qui émet un événement porte sa propre
  file d'événements en attente.** Une entité concernée maintient une
  liste interne (`self._events: list[DomainEvent]`) et expose
  `pull_events() -> list[DomainEvent]`, qui vide la file et la
  retourne. C'est le pattern canonique DDD : une entité est
  responsable de ce qu'elle "raconte" sur elle-même.

- **Chaque repository suit les entités qu'il a chargées ou ajoutées
  pendant la durée de vie du Unit of Work.** Au moment du commit, le
  UoW itère sur ses repositories et collecte les événements en
  attente via `collect_new_events()`, qui appelle `entity.pull_events()`
  sur chaque entité suivie. Cette méthode est **publique** : c'est un
  membre du protocole `EventCollectingRepository`
  (`core/ports/event_publisher.py`), appelé par le UoW à travers une
  frontière d'objet, et les ports de repository concernés
  (`TransactionRepositoryPort`, `BudgetRepositoryPort`,
  `DebtRepositoryPort`) en héritent pour le déclarer. L'implémentation
  unique vit dans `EventTrackingRepository`
  (`core/infrastructure/persistence/event_tracking.py`).

- **Le Unit of Work publie les événements uniquement après un commit
  réussi.** Sur rollback, les événements collectés sont abandonnés
  sans être publiés — c'est le cœur du pattern transactional outbox :
  aucun événement ne sort pour un état qui n'a pas été persisté.

- **L'implémentation par défaut vit dans
  `core/infrastructure/events/in_process_publisher.py`**, un
  adaptateur secondaire générique partagé entre modules. Le
  singleton `bus` actuel peut être conservé en interne de cet
  adaptateur (comme registre d'abonnés), mais n'est plus jamais
  importé directement par du code applicatif — seul le port
  `AbstractEventPublisher` l'est.

## Critères de succès

Cette étape est considérée terminée lorsque les critères suivants
sont tous vérifiés :

- [x] Aucun import de `core.events.bus` dans `finance/application/`
      ni dans `finance/domain/`.
- [x] Les entités de domaine concernées (`Transaction`, `Budget`,
      `Debt`, `SavingsGoal`) exposent une méthode `pull_events()`.
- [x] Les événements sont publiés uniquement après un commit réussi
      du Unit of Work.
- [x] Un test d'intégration vérifie qu'un rollback n'émet aucun
      événement.
- [x] Le `FakeUnitOfWork` utilisé en tests unitaires supporte la même
      mécanique (collecte des événements + publication).
- [x] `FinanceService` n'appelle plus jamais
      `publisher.publish(...)` directement — les entités portent
      leurs événements, le Unit of Work les publie.

## Alternatives

- **Retirer complètement le bus d'événements.** Rejeté : des abonnés
  arriveront (dashboard futur, notifications) — le retirer reviendrait
  sur un mécanisme de découplage inter-module déjà utile en principe,
  seulement sous-exploité pour l'instant.

- **Événements sous forme de `dict`** plutôt que de dataclasses
  typées. Rejeté : typage faible, contrat implicite entre émetteur
  et abonné, empêche le pattern matching côté abonné.

- **Le bus/publisher porté directement par le Unit of Work**, plutôt
  que comme port séparé injecté à côté. Rejeté : mélange les
  responsabilités — le UoW porte les repositories parce qu'ils
  partagent une transaction, l'event publisher est un canal de
  communication séparé, pas un élément de la persistance.

- **Publier les événements directement pendant la transaction**,
  sans pattern outbox. Rejeté : risque de publier un événement pour
  un état qui n'existe finalement pas si la transaction rollback
  ensuite — un bug latent déjà présent dans le code actuel, que ce
  changement ferme explicitement.

- **Reporter le pattern outbox à un ADR futur**, se contenter pour
  l'instant d'injecter le publisher sans transactionnalité. Rejeté :
  l'infrastructure du Unit of Work est déjà en place depuis
  l'ADR-0006, le coût marginal d'ajouter l'outbox maintenant est
  faible (quelques lignes de plus), et le reporter demanderait un
  ADR dédié plus lourd pour un gain de temps minime aujourd'hui.

- **Événements portés par le service applicatif plutôt que par les
  entités.** Rejeté : le service deviendrait responsable de
  "raconter" ce qui appartient au domaine — casse la logique DDD où
  l'entité est propriétaire de ses propres faits métier.

- **Reporter cette étape jusqu'à ce qu'un abonné concret existe**
  (par exemple le dashboard). Rejeté : la dette structurelle actuelle
  (dépendance cachée au singleton) bloque déjà des tests unitaires
  propres et masque une dépendance qui devrait être visible — pas
  besoin d'un abonné réel pour que ce coût soit déjà payé.

## Conséquences

- **Bénéfice fonctionnel réel** : un événement n'est plus jamais
  publié pour un état qui n'existe pas en base — ferme un bug latent
  déjà présent dans le comportement actuel du bus.

- **Coût additionnel de mise en œuvre** par rapport à une version
  simple (publication directe sans outbox) : plus de temps
  d'implémentation, justifié par la fermeture propre de ce bug latent
  plutôt que par un simple déplacement de code.

- **Point d'attention : ne pas sur-utiliser les événements
  d'entité.** Les entités deviennent porteuses d'événements — rester
  vigilant à ne pas transformer chaque mutation en événement publié ;
  seuls les faits métier réellement significatifs le méritent.

- **Référence** : pattern décrit au chapitre 8 de *Architecture
  Patterns with Python* (Percival & Gregory), déjà cité en ADR-0006
  pour le Unit of Work.
