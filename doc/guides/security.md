# Sécurité et Isolation

XCore est conçu avec une approche "Security-First". Ce guide détaille les mécanismes internes de protection, de l'analyse statique à l'isolation au runtime.

## Les Modes d'Exécution

### 1. Mode Trusted (Approuvé)
Le plugin s'exécute dans le même processus que le noyau XCore.
- **Usage** : Plugins internes, code audité, haute performance.
- **Avantages** : Accès direct aux services, pas d'overhead de sérialisation.
- **Risques** : Un bug peut faire planter tout le serveur ; accès total au système de fichiers de l'hôte (si non restreint manuellement).

### 2. Mode Sandboxed (Isolé)
Le plugin s'exécute dans un sous-processus dédié.
- **Usage** : Plugins tiers, code non audité.
- **Isolation** : Via `multiprocessing` et restrictions au niveau de l'OS.

## Analyse Statique (AST Scanner)

Avant même d'être chargé, le code d'un plugin subit un scan AST (Abstract Syntax Tree) pour détecter les comportements dangereux.

### Blocages de l'AST Scanner
L' `ASTScanner` analyse chaque fichier `.py` du dossier `src/` et bloque :
- **Modules interdits** : `os`, `sys`, `subprocess`, `socket`, `importlib`, etc.
- **Built-ins dangereux** : `eval()`, `exec()`, `compile()`, `__import__`, `getattr()`, `setattr()`.
- **Attributs sensibles** : `__class__`, `__globals__`, `__subclasses__`, `__code__`, `__dict__`.
- **Méthodes d'évasion** : Tentatives d'accès à `pathlib.os` ou `importlib.import_module`.

### Configuration de la Whitelist
Vous pouvez autoriser des modules spécifiques dans le `plugin.yaml` :
```yaml
allowed_imports:
  - requests
  - pandas
```

## Isolation au Runtime (FilesystemGuard)

Pour les plugins sandboxed, XCore implémente un `FilesystemGuard` qui utilise le **monkey-patching** pour intercepter les appels au système de fichiers.

### Fonctionnement
Le garde remplace dynamiquement les méthodes de `os` et `pathlib.Path` (ex: `open`, `mkdir`, `unlink`, `rename`, `stat`).
Chaque appel est vérifié par rapport à la politique du plugin :
- **Autorisé par défaut** : Le dossier `data/` du plugin.
- **Interdit par défaut** : Le dossier `src/`, les dossiers parents (`../`), les dossiers système (`/etc`, `/var`).

### Exemple de politique FS
```yaml
filesystem:
  allowed_paths: ["data/", "exports/"]
  denied_paths: ["src/config.py"]
```

## Système de Permissions (ACL)

XCore utilise un système de permissions granulaire pour contrôler l'accès aux ressources du framework (services, autres plugins).

### Syntaxe des règles
Inspiré d'AWS IAM, chaque règle se compose de :
- **Resource** : Le nom de la ressource (ex: `db.users`, `cache.*`, `plugin.auth`).
- **Actions** : Liste d'actions (ex: `read`, `write`, `*`).
- **Effect** : `allow` ou `deny`.

### Exemple dans le manifeste
```yaml
permissions:
  - resource: "db.orders"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.*"
    actions: ["*"]
    effect: allow
  - resource: "plugin.mailer"
    actions: ["send"]
    effect: allow
```

## Signature et Intégrité

Pour les plugins `trusted`, XCore peut exiger une signature numérique pour garantir que le code n'a pas été modifié.

### Signature HMAC-SHA256
Le CLI permet de générer un fichier `plugin.sig` basé sur le hash de tous les fichiers du plugin et une clé secrète partagée.

```bash
xcore plugin sign ./my-plugin --key "${XCORE_SIGNING_KEY}"
```

Le serveur vérifiera cette signature au chargement si `strict_trusted: true` est configuré dans `xcore.yaml`.

## Limitation des Ressources (Sandbox uniquement)

Le mode sandbox permet de définir des limites strictes via l'OS :
- **Mémoire** : `max_memory_mb` (limite la mémoire virtuelle consommée).
- **Temps d'exécution** : `timeout_seconds` par appel d'action.
- **Disque** : `max_disk_mb` (quota sur le dossier data).

```yaml
resources:
  max_memory_mb: 256
  timeout_seconds: 5
```

## Bonnes Pratiques de Sécurité

1. **Principe du moindre privilège** : Ne donnez que les permissions strictement nécessaires dans le manifeste.
2. **Utilisez le mode Sandbox** pour tout plugin dont vous n'avez pas écrit le code vous-même.
3. **Validez les payloads** : Utilisez `@validate_payload` (Pydantic) pour éviter les injections de données malformées.
4. **Secrets** : Ne stockez jamais de clés API en dur. Utilisez les variables d'environnement (`${MY_SECRET}`) qui seront résolues de manière sécurisée par le `ManifestValidator`.
