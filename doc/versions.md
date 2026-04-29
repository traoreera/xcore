# Versions de XCore

## v2.1.2 (Version Actuelle)
- **Stabilité** : Correction de 13 échecs de tests critiques.
- **Sécurité** : Scanner AST amélioré pour détecter les contournements via alias d'imports.
- **Performance** : Intégration de `pytest-benchmark` pour le suivi des performances noyau.
- **Qualité** : Hooks `pre-commit` synchronisés avec `make lint-fix` et tests automatiques.

## v2.0.0
- **Architecture Plugin-First** : Nouveau noyau modulaire.
- **Sandboxing Avancé** : Isolation par sous-processus et FilesystemGuard.
- **Service Container** : Injection de dépendances pour DB, Cache et Scheduler.
- **Middleware Pipeline** : Chaîne d'exécution pré-compilée pour haute performance.
- **SDK Enrichi** : Décorateurs `@action`, `@route`, `@validate_payload`.

## v1.x (Legacy)
- Première version stable basée sur FastAPI.
- Système de plugins monolithique sans isolation.
- Support limité pour les services asynchrones.

## Roadmap Future
- **v2.1.0** : Support natif de gRPC pour l'IPC haute performance.
- **v2.2.0** : Gestionnaire de secrets intégré (Vault).
- **v3.0.0** : Clusterisation multi-nœuds native.
