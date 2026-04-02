# Référence de Configuration

XCore utilise un système de configuration hiérarchique basé sur YAML, avec support des variables d'environnement.

## Structure du fichier `xcore.yaml`

Le fichier de configuration principal est divisé en plusieurs sections clés.

### Section `app`
Configuration globale de l'application.

| Clé | Description | Défaut |
|-----|-------------|--------|
| `env` | Environnement (`development`, `production`, `test`) | `development` |
| `debug` | Active le mode debug (logs détaillés, etc.) | `false` |
| `secret_key` | Clé utilisée pour le hachage et la signature. | - |
| `plugin_dir` | Répertoire où sont stockés les plugins. | `plugins/` |
| `plugin_prefix` | Préfixe URL pour les endpoints IPC des plugins. | `/app` |

### Section `database`
Configuration de la persistance SQL.

```yaml
database:
  enabled: true
  url: "postgresql://user:pass@localhost/db"
  pool_size: 20
  max_overflow: 10
  echo: false # Affiche les requêtes SQL (debug)
```

### Section `cache`
Configuration de Redis ou du cache en mémoire.

```yaml
cache:
  backend: "redis" # "redis" ou "memory"
  url: "redis://localhost:6379/0"
  ttl_default: 3600
  prefix: "xcore:"
```

### Section `scheduler`
Configuration de l'APScheduler.

```yaml
scheduler:
  enabled: true
  timezone: "UTC"
  thread_pool_size: 10
```

### Section `plugins`
Paramètres globaux du système de plugins.

| Clé | Description | Défaut |
|-----|-------------|--------|
| `strict_trusted` | Force la vérification de signature pour les plugins Trusted. | `false` |
| `allow_hot_reload` | Active le rechargement automatique lors de la modification de fichiers. | `true` |
| `default_mode` | Mode d'exécution par défaut (`sandboxed` ou `trusted`). | `sandboxed` |
| `scan_interval` | Intervalle de scan du répertoire plugins (en secondes). | `5` |

---

## Configuration du Plugin (`plugin.yaml`)

Chaque plugin possède son propre manifeste définissant son identité et ses contraintes.

### Métadonnées de base
```yaml
name: mon_plugin
version: "1.2.0"
author: "Equipe XCore"
description: "Description courte du plugin"
execution_mode: "sandboxed" # ou "trusted"
entry_point: "src/main.py"
```

### Section `resources` (Sandbox uniquement)
Définit les limites imposées au sous-processus.

```yaml
resources:
  timeout_seconds: 30     # Temps max pour un appel IPC
  max_memory_mb: 256      # Limite mémoire (RLIMIT_AS)
  max_disk_mb: 100        # Quota disque (indicatif)
  rate_limit:
    calls: 100            # Nombre d'appels
    period_seconds: 60    # Par fenêtre de temps
```

### Section `permissions`
Liste les droits d'accès aux ressources du système.

```yaml
permissions:
  - resource: "cache.user_*"
    actions: ["read", "write"]
    effect: allow
  - resource: "db.finance"
    actions: ["*"]
    effect: deny
```

### Section `env`
Variables d'environnement injectées dans le plugin. Supporte l'interpolation `${VAR}` depuis l'environnement système.

```yaml
env:
  API_TOKEN: "${EXTERNAL_API_TOKEN}"
  LOG_LEVEL: "INFO"
```

### Section `filesystem` (Sandbox uniquement)
```yaml
filesystem:
  allowed_paths: ["data/"]
  denied_paths: ["src/", ".git/"]
```

---

## Remplacement par Variables d'Environnement

Toutes les valeurs de `xcore.yaml` peuvent être surchargées par des variables d'environnement avec le préfixe `XCORE__` et un double underscore pour la hiérarchie.

Exemple :
`XCORE__DATABASE__URL="sqlite:///prod.db"` surchargera la clé `url` de la section `database`.
