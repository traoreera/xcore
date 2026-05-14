# Versions

## v2.3.0 — Actuelle (2026-05-14)

### Multi-Tenancy natif (Axe 1)

- **`TenantMiddleware`** — extrait le `tenant_id` depuis le header HTTP (`X-Tenant-ID`) ou le sous-domaine ; injecte `request.state.tenant_id` sur chaque requête.
- **`TenantAwareCache`** — wrappe le cache et préfixe automatiquement toutes les clés par `{tenant_id}:`. Méthodes : `get`, `set`, `delete`, `exists`, `incr`, `keys`, `clear`.
- **`TenantAwareDB`** — wrappe les adapters SQL et exécute `SET search_path TO {tenant_id}, public` (PostgreSQL) avant chaque requête. Détection automatique de tous les adapters nommés (`AsyncSQLAdapter`, `MongoDBAdapter`…).
- **`TenantAwareScheduler`** — préfixe les `job_id` APScheduler par `{tenant_id}:` ; `get_jobs()` filtre les jobs au tenant courant.
- **`wrap_services_for_tenant()`** — remplace les services dans le contexte plugin à chaque appel ; zéro changement de code pour les plugins existants.

### Autorisation IPC (`allowed_callers`)

- **`IPCAuthMiddleware`** — premier middleware de la pipeline ; vérifie `allowed_callers` déclaré dans `plugin.yaml` avant tout traitement.
- **Deny-by-default** — liste vide ou absente = tout appel IPC refusé. Les appels HTTP directs (`caller=None`) passent toujours.
- **`PluginLoader.get_manifest(name)`** — méthode ajoutée pour accéder au manifeste depuis le middleware.

### `@schema` — Décorateur versionné avec validation intégrée (Axe 3)

- **`@schema(version, input, output, …)`** — combine documentation du schéma ET validation Pydantic en un seul décorateur (source unique de vérité).
- **`SchemaRegistry`** — singleton qui stocke tous les schémas déclarés par `@schema`.
- **`BreakingChangeDetector`** — détecte les breaking changes entre deux versions du registre (action supprimée, champ supprimé, type modifié).
- **`xcore plugin validate --check-breaking schemas_v1.json`** — commande CLI pour comparer les schémas.

### Configuration

- Section `tenancy:` dans `integration.yaml` avec 8 flags : `enabled`, `header`, `subdomain`, `default_tenant`, `isolate_cache`, `isolate_db`, `isolate_scheduler`, `enforce_ipc`.
- `TenancyConfig` dataclass dans `configurations/sections.py`.
- `allowed_callers: list[str]` ajouté à `PluginManifest`.

### Tests

- **58 nouveaux tests** : `tests/unit/kernel/test_tenancy.py` (41) et `tests/integration/test_tenancy_integration.py` (17).

### Documentation

- `doc/guides/tenancy.md` — guide complet multi-tenancy avec exemples.
- `doc/guides/plugin-manifest.md` — référence de `plugin.yaml` avec tous les champs.
- `doc/reference/configuration.md` — section `tenancy:` documentée.
- `doc/reference/sdk.md` — `@schema` documenté.
- `doc/guides/security.md` — section `allowed_callers` et IPC.
- `doc/architecture/decisions.md` — décisions 7 (tenancy), 8 (IPC deny-by-default), 9 (`@schema` source unique).

---

## v2.2.0 — (2026-05-14)
**Security Release & Dependency Optimization**

- 🛡️ **Sécurité** : Suppression de `python-jose` et `python-ecdsa` pour éliminer la vulnérabilité aux attaques temporelles Minerva (CVE-2024-23342).
- 🧹 **Nettoyage** : Retrait de 7 dépendances inutilisées dans le noyau (`pillow`, `watchdog`, `user-agents`, `aiocache`, `toml`, `mysql-connector-python`).
- ⚡ **Optimisation** : Déplacement de `psutil` en dépendance de développement et `markdown` en dépendance de documentation.
- 📦 **Minimalisme** : Le framework est maintenant plus léger de ~15 Mo et possède une surface d'attaque réduite.

## v2.1.3 (2026-05-13)

### XWorker (Celery natif)
- Intégration Celery complète dans le `ServiceContainer` — activé via `services.xworker.enabled: true`
- Bootstrap automatique de `_celery_worker` à l'import pour que `celery -A xcore.services.xworker.xworker:_celery_worker` fonctionne directement
- Fix broker : `broker=` passé au constructeur `Celery()`, fin du fallback AMQP
- Décorateur `@task()` compatible avec le registry, enregistrement paresseux avant `boot()`

### CLI `xcore worker`
- Gestion complète des processus FastAPI (uvicorn) et Celery en arrière-plan
- Fichiers PID dans `.xcore/pids/`, logs dans `log/`
- Commandes : `start`, `stop`, `status`, `logs --follow`, `inspect`, `purge`, `beat`
- Valeurs par défaut lues depuis `integration.yaml` (sections `app.server` et `services.xworker`)

### Configuration étendue
- `app.fastapi` — tous les paramètres du constructeur `FastAPI()` configurables dans le YAML
- `app.server` — paramètres uvicorn (`host`, `port`, `workers`, `reload`, `log_level`…)

### Système de middlewares déclaratifs
- Chargement automatique depuis `integration.yaml → middleware`
- Params `external` (valeur directe) et `internal` (service résolu paresseusement)
- `Xcore.setup(app)` — à appeler après `FastAPI()`, avant uvicorn
- Middlewares intégrés : `RequestTimingMiddleware`, `CacheHeaderMiddleware`

---

## v2.1.2 — (2026-04-29)

### Corrections
- 13 échecs de tests critiques résolus (kernel, permissions, sandbox).
- Scanner AST : détection des contournements via alias d'imports (`import os as système`).

### Performances
- Cache LRU sur `PermissionEngine` : **+34 % de débit**, latence moyenne 113 µs (vs 152 µs sans cache).
- `mset`/`mget` natif sur `RedisCacheBackend` : **44× plus rapide** sur les SET batch, **77×** sur GET.
- Compilation regex pré-calculée dans `Policy.matches()` : short-circuit action en **0.4 µs**.

### Qualité
- `pytest-benchmark` intégré pour le suivi continu des performances.
- Hooks `pre-commit` synchronisés : `black` + `isort` + `flake8` + tests automatiques au commit.
- `pyproject.toml` migré vers PEP 621 (`[project]`) — compatible Poetry 2.x.

### Chiffres mesurés (Python 3.14)

| Composant | Métrique | Valeur |
|:----------|:---------|-------:|
| `Policy.matches` — match | Latence moy. | 1.6 µs |
| `Policy.matches` — short-circuit action | Latence moy. | 0.4 µs |
| `PermissionEngine` avec cache (6 checks) | Latence moy. | 113 µs |
| `PermissionEngine` sans cache (6 checks) | Latence moy. | 152 µs |
| `Redis mset` 100 clés (2 ms réseau) | Latence totale | 5.3 ms |
| `Redis sequential set` 100 clés | Latence totale | 232 ms |

→ [Page Benchmarks complète](reference/benchmarks.md)

---

## v2.0.0

- **Architecture Plugin-First** : noyau modulaire, séparation Kernel / Services / Plugins.
- **Sandboxing avancé** : isolation par sous-processus OS, communication JSON-RPC 2.0.
- **ServiceContainer** : injection de dépendances pour DB (SQLAlchemy 2.0), Cache (Redis/Memory), Scheduler (APScheduler).
- **MiddlewarePipeline** : chaîne Tracing → RateLimit → Permissions → Retry pré-compilée.
- **SDK enrichi** : décorateurs `@action`, `@route`, `@validate_payload`, `AutoDispatchMixin`, `RoutedPlugin`.
- **RBAC** : `AuthBackend` pluggable + `RBACChecker` déclaratif sur les routes.
- **StateMachine** : FSM par plugin avec transitions validées.
- **PluginRegistry** : métadonnées, dépendances, versioning semver.

---

## v1.x — Legacy

- Première version stable basée sur FastAPI.
- Système de plugins monolithique sans isolation.
- Support limité pour les services asynchrones.

---

## Roadmap

| Version | Fonctionnalité prévue |
|:--------|:----------------------|
| **v2.4.0** | Plugin Federation (Axe 2) — appels cross-instances |
| **v2.5.0** | AgentBase (Axe 4) — plugins IA avec mémoire et outils |
| **v2.6.0** | Hot-swap de services (Axe 5) — remplacement sans redémarrage |
| **v3.0.0** | OpenTelemetry natif (Axe 7) + Clusterisation multi-nœuds |
