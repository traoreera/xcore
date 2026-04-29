# Versions

## v2.1.2 — Actuelle (2026-04-29)

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
| **v2.2.0** | Gestionnaire de secrets intégré (Vault / SOPS) |
| **v2.3.0** | Support natif gRPC pour l'IPC haute performance |
| **v3.0.0** | Clusterisation multi-nœuds native |
