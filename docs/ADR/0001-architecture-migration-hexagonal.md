# 001- Migration vers une architecture Port-Adaptateur (Hexagonal)

- **Statut** : Accepté
- **Date** : 2026-09-12

## Contexte

LifeManager est un projet personnel servant de laboratoire
d'expérimentation architecturale. Le module Finance est actuellement
implémenté selon l'architecture 5-couches MVC décrite dans le
`CLAUDE.md` du projet (Présentation → Contrôleurs → Services →
Repositories → PostgreSQL), avec un backend complet et fonctionnel :
6 repositories, `FinanceService` couvrant les cas d'usage principaux,
22 tests unitaires verts. 

Cette architecture ne présente aujourd'hui aucune limite fonctionnelle ou de maintenabilité bloquante : les règles de séparation (services sans Qt, vues sans accès direct aux repositories) sont respectées et l'ensemble est suffisant en l'état. Un audit préalable a néanmoins identifié 14 fuites structurelles (entités ORM traversant l'UI, service typé sur Session, singletons créés à l'import), dont la synthèse est disponible dans ([Notion — Audit](https://app.notion.com/p/Audit-3d9e2e7cbdf781e7937de8649328bdbe?source=copy_link)).

La motivation de ce changement n'est donc pas corrective mais
formative : ce projet sert de terrain d'expérimentation pour étudier
l'architecture Port-Adaptateur (Hexagonale) — ses problématiques,
son fonctionnement, ses contraintes de déploiement — en amont d'une
prise de poste en CDI (suite à un stage) où je serai améné à adopter cette architecture.



## Décision

LifeManager migre de l'architecture 5-couches MVC vers une architecture
Port-Adaptateur (Hexagonale), appliquée à l'ensemble des modules existants
et futurs (Finance en premier, puis Grocery, Nutrition, etc.).

Concrètement :

- Le **domaine** (entités + logique métier, ex. `FinanceService` actuel)
  ne dépend plus d'aucune brique technique — ni Qt, ni SQLAlchemy, ni
  `requests`. Il n'importe que des **ports**.
- Un **port** est une interface définie côté domaine,
  qui décrit un besoin métier sans dire comment il est satisfait
  (ex. `TransactionRepositoryPort.get_by_month(...)`).
- Un **adaptateur** est une implémentation concrète d'un port, côté
  infrastructure : `SQLAlchemyTransactionAdapter`, `OpenFoodFactsAdapter`,
  `PyQt6TransactionView` (adaptateur "primaire", côté UI).
- Les repositories SQLAlchemy actuels (`BaseRepository[T]` et ses
  sous-classes) deviennent des adaptateurs secondaires implémentant les
  ports définis par le domaine — l'inversion de dépendance se fait à
  cette frontière.
- Chaque module (`finance/`, `grocery/`, `nutrition/`) expose son propre
  ensemble de ports et reçoit ses propres adaptateurs ; aucun module ne
  dépend directement d'un adaptateur d'un autre module.


La migration se fait module par module, en commençant par `finance/`
puisqu'il est le plus abouti.


## Critères de succès

La migration sera considérée comme respectée si les règles suivantes
sont vérifiables (par grep, import-linter ou exécution de tests) sur
le module Finance à l'issue de la première itération, puis maintenues
sur les modules suivants :

- Aucun import `sqlalchemy` dans le package `domain/`
- Aucun import `PyQt6` dans les packages `domain/` et `application/`
- Aucun import `requests` (ou autre client HTTP) dans `domain/` et `application/`
- Les tests du domaine s'exécutent sans démarrer PostgreSQL
- Un nouveau module métier (grocery, nutrition) peut être écrit
  sans modifier `core/` ni `finance/`
- Chaque adaptateur secondaire (SQLAlchemy, HTTP) peut être remplacé
  sans modifier le domaine ni les use-cases

## Alternatives

- **Maintenir l'architecture 5-couches MVC actuelle.** Demanderait
  moins d'effort, mais ne contribue pas à l'objectif de montée en
  compétence sur une nouvelle architecture. Par ailleurs, le MVC ne
  fait pas ressortir aussi nettement la frontière entre logique
  métier et dépendances externes (UI, base de données, API) — les
  services dépendent directement des repositories concrets plutôt
  que d'une interface définie côté domaine.

- **Durcir le MVC existant** en introduisant des interfaces
  (`Protocol`) entre Services et Repositories sans changer la
  structure en couches. Réduirait une partie du couplage à moindre
  coût, mais resterait un compromis à mi-chemin : ne fait pas
  travailler la séparation ports/adaptateurs de bout en bout
  (y compris côté UI), donc n'atteint pas l'objectif de montée en
  compétence sur l'hexagonal complet.

- **Clean Architecture ou DDD tactique complet.** Architecture
  probablement la plus adaptée à la multiplicité des modules du
  projet, mais correspond à un niveau de sur-ingénierie encore
  supérieur à celui de l'hexagonal, non justifié à l'état actuel.
  Peut faire l'objet d'une évolution future si la complexité du
  projet le justifie.

- **Architecture micro-services.** Écartée pour les mêmes raisons :
  sur-ingénierie disproportionnée pour un projet personnel mono-
  utilisateur et mono-déploiement, à réévaluer seulement si le
  projet évoluait vers un contexte multi-utilisateur ou distribué.


## Conséquences

- **Domaine testable et remplaçable indépendamment de l'infrastructure** :
  le domaine (`FinanceService` et les futurs services des autres
  modules) pourra être testé en mockant des ports plutôt que la
  session SQLAlchemy, et l'adaptateur PostgreSQL/SQLAlchemy pourra en
  théorie être remplacé (autre store, autre ORM) sans modifier la
  logique métier — corrige la limite actuelle où les services
  dépendent directement des repositories concrets.
  
- **Coût de développement accru** : environ un mois pour un premier
  jet fonctionnel du module Finance migré et déployé, puis jusqu'à 3 mois pour
  l'ensemble de la roadmap de refactoring détaillée dans l'audit
  ([Notion — Audit](https://app.notion.com/p/Audit-3d9e2e7cbdf781e7937de8649328bdbe?source=copy_link)).

- **Complexité accrue et risque de sur-ingénierie**, en particulier
  en début de migration : plus de fichiers et d'indirections
  (port + adaptateur là où un accès direct suffisait), à surveiller
  pour ne pas dépasser ce que la taille réelle du projet justifie.

## Status