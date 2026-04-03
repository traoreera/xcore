# Versions de XCore

## v2.0.0 (Version Actuelle)
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
