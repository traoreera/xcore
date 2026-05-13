# Changelog

Toutes les modifications notables de xcore sont documentées ici.

Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).
Versionnage selon [Semantic Versioning](https://semver.org/lang/fr/).

---

## [2.1.3] — 2026-05-13

### Ajouté
- **Service XWorker** — intégration native de Celery dans le `ServiceContainer` via `XWorkerServiceProvider` ; activé avec `services.xworker.enabled: true` dans `integration.yaml`
- **CLI `xcore worker`** — gestion complète des processus FastAPI et Celery en processus séparés :
  - `xcore worker start [api|celery]` — lance uvicorn et/ou le worker Celery
  - `xcore worker stop [api|celery]` — arrêt propre via fichiers PID (`.xcore/pids/`)
  - `xcore worker status` — état des processus avec sortie JSON optionnelle
  - `xcore worker logs [api|celery]` — tail des logs avec `--follow`
  - `xcore worker inspect` — liste les tâches enregistrées et les workers actifs
  - `xcore worker purge [queue]` — vide une file d'attente Celery
  - `xcore worker beat` — lance le scheduler Celery Beat
- **`WorkerConfig`** dans `sections.py` — configuration typée avec synchronisation `modules` ↔ `task_list` et méthode `to_payload()`
- **Overload de typage** `container.get("worker") → WorkerService` dans `ServiceContainer`
- **Suite de tests** pour `WorkerConfig`, `WorkerService`, `task registry` et `XWorkerServiceProvider` (54 tests)

### Modifié
- `ServiceContainer.DEFAULT_PROVIDERS` inclut maintenant `XWorkerServiceProvider` (5 providers)
- `ServicesConfig` accepte les clés `xworker` et `celery` (alias) dans `integration.yaml`

---

## [2.1.2] — 2025-10-xx

### Ajouté
- **Devcontainer** — configuration `.devcontainer/` pour VS Code et GitHub Codespaces
- **Audit de sécurité 2.1.2** — politique de sécurité mise à jour (`SECURITY.md`)
- Plugin virtuel `kernel` pour prendre en charge les commandes internes du framework

### Modifié
- Refonte complète de la documentation technique (FR)
- Chemins par défaut migrés de `xcore.*` vers `integration.*`
- Suppression des `print` restants remplacés par le logger

### Corrigé
- Bug dans `plugin cmd` — rechargement à chaud défaillant dans certains cas
- Injection de la configuration YAML du sandbox dans le runtime du plugin sous forme de dictionnaire

---

## [2.1.1] — 2025-xx-xx

### Ajouté
- **Middlewares sandbox** — architecture de middlewares pour les plugins (permissions, ratelimit, retry, tracing)
- **`FilesystemGuard`** renforcé avec isolation accrue du worker sandbox
- Limites de ressources CPU/mémoire via le module `resource` dans le `SandboxProcessManager`
- `StateManager` configurable — support de plusieurs états personnalisables

### Corrigé
- Audit de sécurité sandbox — blocage des builtins et modules dangereux
- Correction de la logique de vérification des signatures dans `TrustedActivator`

---

## [2.0.2] — 2025-xx-xx

### Ajouté
- **`RouterRegistry`** — facilite la création de routes FastAPI avec un décorateur `route` unifié par méthode HTTP
- **RBAC** — base de contrôle d'accès par rôle sans logique métier, prête à être étendue par les plugins
- Amélioration UX du CLI sandbox avec Rich (tables, panels)

### Corrigé
- **[HIGH]** Hachage faible dans `worker.py` — migration vers un algorithme sécurisé (#116)
- **[MEDIUM]** SSRF/LFI dans le CLI et le marketplace (#112)
- Optimisation des opérations batch du backend mémoire (#111)

---

## [2.0.1] — 2025-xx-xx

### Ajouté
- **`KernelContext` unifié** — refactorisation du kernel pour un contexte centralisé et découplé
- **`EventBus`** avec dispatch optimisé — pré-compilation des wildcards et lookup exact
- **`MiddlewarePipeline`** — compilation des closures à l'enregistrement, suppression des surcoûts par appel

### Corrigé
- **[HIGH]** Bypass de signature de plugin via `entry_point` (#158)
- **[HIGH]** Path traversal dans `FilesystemGuard` via la configuration du manifeste (#161)
- **[HIGH]** Bypass du scanner AST via `entry_point` personnalisé (#152)
- Optimisation du matching de permissions (#153)

---

## [1.0.0] — 2025-xx-xx

### Ajouté
- Architecture plugin-first sur FastAPI avec `BasePlugin` (sandboxé) et `TrustedBase` (accès complet)
- `ServiceContainer` avec providers pour database, cache, scheduler et extensions
- `EventBus` pour la communication kernel ↔ plugins
- `HookManager` pour les hooks pre/post sur les événements
- `PluginRegistry` — découverte et versionnage des plugins
- Sandbox AST — scan des imports et restrictions pour les plugins non signés
- Signature HMAC-SHA256 des plugins Trusted (`sign_plugin`, `verify_plugin`)
- CLI `xcore` avec gestion des plugins, sandbox et marketplace
- Support multi-base de données : PostgreSQL, MySQL, SQLite, MongoDB, Redis
- Cache Redis (hiredis) et mémoire via aiocache
- Scheduler APScheduler avec backends memory, redis, database
- Observabilité : logging structuré, métriques, tracing OpenTelemetry
- Marketplace client pour la découverte et l'installation de plugins externes

---

[2.1.3]: https://github.com/traoreera/xcore/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/traoreera/xcore/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/traoreera/xcore/compare/v2.0.2...v2.1.1
[2.0.2]: https://github.com/traoreera/xcore/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/traoreera/xcore/compare/v1...v2.0.1
[1.0.0]: https://github.com/traoreera/xcore/releases/tag/v1
