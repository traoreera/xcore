# Choix Techniques et Architecture de Décision (ADR)

Ce document documente les choix architecturaux majeurs pris lors du développement d'XCore.

## Choix du Sandboxing (Subprocess vs Isolation de Mémoire)

**Décision :** Utiliser des sous-processus isolés pour le mode `sandboxed`.

**Raisonnement :**
- Contrairement à l'isolation par modules (qui peut être contournée via `sys.modules` ou `__builtins__`), les sous-processus offrent une isolation stricte au niveau de l'OS.
- Permet l'utilisation de `RLIMIT` (CPU, Mémoire) nativement sur Linux.
- Facilite la gestion de la fin des processus en cas de bug ou de boucle infinie dans un plugin.

**Compromis :** Coût de performance lié à la sérialisation (IPC) et au démarrage des processus (~1-5ms d'overhead par appel).

## Pattern Middleware de PluginSupervisor

**Décision :** Implémenter une pipeline de middleware asynchrone pour intercepter chaque appel à un plugin.

**Raisonnement :**
- Permet d'ajouter des fonctionnalités transversales (Tracing, Rate Limiting, Permissions, Logging) de manière modulaire sans modifier le code des plugins.
- Offre un contrôle total sur l'exécution : un middleware peut annuler un appel (ex: PermissionDenied) ou le relancer (ex: RetryMiddleware).

**Optimisation :** La chaîne de middleware est pré-compilée lors de l'initialisation pour éviter la récursion dynamique à chaque appel.

## Synchronisation du Rate Limiter

**Décision :** Utiliser des opérations synchrones en mémoire pour le `RateLimiter`.

**Raisonnement :**
- Le Rate Limiting est sur le chemin critique de l'exécution.
- L'utilisation de verrous asynchrones (`asyncio.Lock`) introduisait un overhead significatif.
- En passant en synchrone et en optimisant les structures de données, le gain de performance a été mesuré à ~55% sur le "hot-path".

## Système de Permissions (ACL)

**Décision :** Utiliser une syntaxe déclarative inspirée d'AWS IAM dans le manifeste des plugins.

**Raisonnement :**
- Facile à comprendre pour les développeurs.
- Permet une validation statique du manifeste.
- Supporte nativement les wildcards (`*`) pour les ressources et les actions.

## FilesystemGuard via Monkey-Patching

**Décision :** Intercepter les appels système `os` et `pathlib` dans le sandbox via monkey-patching.

**Raisonnement :**
- Permet d'autoriser l'accès uniquement au dossier `data/` du plugin.
- Plus simple à mettre en œuvre que des systèmes de fichiers virtuels complexes tout en restant robuste pour du code Python standard.
- Utilise `inspect.signature` pour garantir que les arguments de chemin (positionnels ou par mot-clé) sont correctement interceptés.
