# Options de configuration

xcore est configuré via `config.json` à la racine du projet et via des variables d'environnement.

---

## `config.json` — Configuration globale

```json
{
  "app": {
    "name": "xcore",
    "version": "1.0.0",
    "debug": false,
    "host": "0.0.0.0",
    "port": 8000
  },
  "database": {
    "url": "sqlite:///./xcore.db",
    "pool_size": 5,
    "echo": false
  },
  "cache": {
    "enabled": true,
    "redis_url": "redis://localhost:6379/0",
    "default_ttl": 300
  },
  "auth": {
    "secret_key": "changez-moi-en-production",
    "algorithm": "HS256",
    "access_token_expire_minutes": 60
  },
  "plugins": {
    "directory": "plugins",
    "auto_load": true,
    "sandbox": {
      "enabled": false,
      "max_memory_mb": 256,
      "max_cpu_seconds": 30
    }
  },
  "scheduler": {
    "enabled": true,
    "max_workers": 4
  },
  "logging": {
    "level": "INFO",
    "format": "colored",
    "file": null
  }
}
```

---

## Référence des champs

### Section `app`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `name` | `str` | `"xcore"` | Nom de l'application |
| `version` | `str` | `"1.0.0"` | Version de l'application |
| `debug` | `bool` | `false` | Mode debug (logs détaillés, rechargement auto) |
| `host` | `str` | `"0.0.0.0"` | Adresse d'écoute du serveur |
| `port` | `int` | `8000` | Port d'écoute |

### Section `database`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `url` | `str` | SQLite local | URL de connexion SQLAlchemy |
| `pool_size` | `int` | `5` | Taille du pool de connexions |
| `echo` | `bool` | `false` | Logger les requêtes SQL (debug) |

Exemples d'URL :
```
sqlite:///./xcore.db
postgresql://user:pass@localhost/dbname
mysql+pymysql://user:pass@localhost/dbname
```

### Section `cache`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `enabled` | `bool` | `true` | Activer le cache Redis |
| `redis_url` | `str` | `redis://localhost:6379/0` | URL Redis |
| `default_ttl` | `int` | `300` | TTL par défaut en secondes |

### Section `auth`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `secret_key` | `str` | — | **À changer en production** — clé de signature JWT |
| `algorithm` | `str` | `"HS256"` | Algorithme JWT |
| `access_token_expire_minutes` | `int` | `60` | Durée de vie du token (minutes) |

### Section `plugins`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `directory` | `str` | `"plugins"` | Dossier de découverte des plugins |
| `auto_load` | `bool` | `true` | Charger automatiquement tous les plugins au démarrage |
| `sandbox.enabled` | `bool` | `false` | Activer l'isolation des plugins |
| `sandbox.max_memory_mb` | `int` | `256` | Quota mémoire par plugin (sandbox) |
| `sandbox.max_cpu_seconds` | `int` | `30` | Quota CPU par plugin (sandbox) |

### Section `scheduler`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `enabled` | `bool` | `true` | Activer le scheduler de tâches |
| `max_workers` | `int` | `4` | Nombre de workers parallèles |

### Section `logging`

| Champ | Type | Défaut | Description |
|-------|------|--------|-------------|
| `level` | `str` | `"INFO"` | Niveau de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `format` | `str` | `"colored"` | Format : `"colored"` (dev) ou `"json"` (prod) |
| `file` | `str\|null` | `null` | Chemin vers un fichier de log (null = stdout) |

---

## Variables d'environnement

Les variables d'environnement **surchargent** les valeurs de `config.json` :

| Variable | Correspond à |
|----------|-------------|
| `DATABASE_URL` | `database.url` |
| `REDIS_URL` | `cache.redis_url` |
| `SECRET_KEY` | `auth.secret_key` |
| `DEBUG` | `app.debug` |
| `PLUGINS_DIR` | `plugins.directory` |

En production, utilisez un fichier `.env` :

```bash
# .env
SECRET_KEY=une-cle-tres-secrete-et-longue
DATABASE_URL=postgresql://user:pass@db:5432/xcore
REDIS_URL=redis://redis:6379/0
DEBUG=false
```

---

## Configuration par plugin

Chaque plugin peut avoir son propre `config.yaml`. Voir [Anatomie d'un plugin](./plugin-anatomy.md) pour la référence complète.
