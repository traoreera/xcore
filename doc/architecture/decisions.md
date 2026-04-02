# Choix Techniques et Architecture

Ce document détaille les décisions architecturales majeures prises lors de la conception du framework XCore v2, ainsi que les compromis (trade-offs) effectués.

## Philosophie : "Plugin-First" et Noyau Minimal

XCore a été conçu avec la conviction que la logique métier ne doit pas polluer le noyau du framework. Le noyau (Kernel) n'est qu'un orchestrateur fournissant :
- Un système de chargement et de cycle de vie.
- Un bus d'événements et de hooks.
- Un accès sécurisé à des services partagés (DB, Cache, Scheduler).
- Une couche de sécurité (Sandboxing, Permissions).

## Choix de FastAPI

Le choix de **FastAPI** comme fondation repose sur plusieurs facteurs :
- **Performance** : Performance exceptionnelle grâce à `starlette` et `pydantic`.
- **Ecosystème** : Compatibilité native avec l'asynchrone (ASGI) et typage fort.
- **Documentation automatique** : Génération OpenAPI (Swagger) immédiate, cruciale pour un framework de plugins.
- **Flexibilité** : Facilité d'injection de routers dynamiques.

## Isolation des Plugins : Trusted vs Sandboxed

L'une des décisions les plus critiques a été le choix du modèle d'isolation.

### 1. Mode Trusted (Processus Principal)
- **Pourquoi** : Pour les extensions de confiance nécessitant une performance maximale et un accès direct aux services.
- **Mécanisme** : Chargement dynamique via `importlib`.
- **Avantage** : Zéro surcharge (overhead) de communication, partage de mémoire.
- **Inconvénient** : Une erreur critique peut faire tomber le serveur entier.

### 2. Mode Sandboxed (Sous-processus Isolé)
- **Pourquoi** : Pour exécuter du code tiers ou non audité en toute sécurité.
- **Mécanisme** : Chaque plugin tourne dans un processus `multiprocessing` séparé.
- **Sécurité** :
    - **AST Scanning** : Analyse statique du code pour bloquer les imports/appels dangereux.
    - **FilesystemGuard** : Monkey-patching de `os` et `pathlib` pour restreindre l'accès au disque.
    - **Import Hook** : Namespace isolé (`xcore_plugin_<uid>`) pour éviter les conflits de modules.
    - **IPC** : Communication via JSON-RPC sur tubes (pipes).

## Pipeline de Middlewares

XCore utilise un pattern **Middleware Pipeline** pour les appels de plugins (`supervisor.call`). Cela permet une séparation nette des préoccupations (Separation of Concerns) :
1. **TracingMiddleware** : Observabilité et corrélation des appels.
2. **RateLimitMiddleware** : Protection contre les abus.
3. **PermissionMiddleware** : Vérification des droits d'exécution.
4. **RetryMiddleware** : Résilience face aux erreurs transitoires (backoff exponentiel).

## Système de Permissions (RBAC/ABAC)

Au lieu d'un simple système binaire (autorisé/refusé), XCore implémente un moteur de permissions capable de :
- Utiliser des **globs** pour les ressources (ex: `cache.*`).
- Définir des actions précises (ex: `read`, `write`, `execute`).
- Appliquer des effets `allow` ou `deny`.
- **Optimisation** : Les résultats sont mémoïsés pour réduire l'overhead des comparaisons de patterns à ~16µs.

## Gestion de la Performance

Des optimisations constantes sont appliquées sur le "hot-path" (chemin d'exécution critique) :
- **Suppression du verrou asyncio** dans le Rate Limiter pour les opérations purement en mémoire.
- **Bypass de la machine à états** (`RUNNING`) lors des appels pour permettre la concurrence et réduire la latence de ~20%.
- **Caching du statut `is_async`** des handlers d'événements pour éviter les appels répétés à `inspect`.

## Choix de Persistance

XCore privilégie l'abstraction via des **Providers** :
- **SQL** : Support de SQLAlchemy (Sync/Async) pour PostgreSQL, MySQL et SQLite.
- **NoSQL** : Redis pour le cache et la coordination distribuée.
- **Batching** : Implémentation native de `mget`/`mset` dans le SDK pour réduire les allers-retours réseau.

## Évolutions Futures

- **WebAssembly (WASM)** : Exploration de l'isolation via `wasmer-python` pour une sécurité encore plus granulaire.
- **Service Mesh** : Intégration native avec des protocoles comme gRPC pour les communications inter-plugins distribuées.
