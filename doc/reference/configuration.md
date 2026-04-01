# Référence de Configuration (Détaillée)

Cette section détaille chaque paramètre de configuration de XCore. Toutes les valeurs peuvent être injectées via des variables d'environnement (`${VAR}`).

## 1. Section `app` (Framework)

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `name` | requis | Nom de l'application (pour les logs/métriques). |
| `env` | `dev` | `development`, `staging`, `production`. |
| `debug` | `false` | Active les traces d'erreurs détaillées et logs `DEBUG`. |
| `secret_key` | requis | Clé HMAC (min 32 chars) pour les sessions et JWT. |
| `plugin_prefix` | `/plugins` | Préfixe URL pour les routes exposées par les plugins. |
| `dotenv` | `null` | Chemin vers un fichier `.env` global. |

## 2. Section `plugins` (Runtime)

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `directory` | `./plugins` | Dossier source des plugins. |
| `strict_trusted` | `false` | Si `true`, rejette les plugins `trusted` non signés. |
| `interval` | `0` | Intervalle de scan pour le rechargement à chaud (0 = off). |
| `entry_point` | `src/main.py` | Nom du fichier principal du plugin. |
| `secret_key` | `null` | Clé pour la vérification des signatures (`plugin.sig`). |

## 3. Section `services` (Core)

### `databases` (SQL & NoSQL)
Backends supportés : `postgresql`, `mysql`, `sqlite`, `redis`.

**PostgreSQL (Sync/Async) :**
```yaml
databases:
  main:
    type: postgresql
    url: "${DATABASE_URL}"
    pool_size: 20
    max_overflow: 10
    pool_recycle: 3600
  async_db:
    type: sqlasync
    url: "${DATABASE_ASYNC_URL}"
```

### `cache` (Redis / Memory)
```yaml
cache:
  backend: "redis" # ou "memory"
  url: "${REDIS_URL}"
  ttl: 300
  prefix: "xcore:"
  max_size: 10000 # pour le mode memory uniquement
```

### `scheduler` (APScheduler)
```yaml
scheduler:
  enabled: true
  backend: "redis" # partage des tâches entre instances
  timezone: "UTC"
```

## 4. Section `observability` (Monitoring)

### `logging`
```yaml
logging:
  level: "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "json" # ou "text"
  file: "/var/log/xcore.log"
  max_bytes: 10485760 # 10 MB rotation
```

### `metrics`
```yaml
metrics:
  enabled: true
  backend: "prometheus"
  port: 9090
```

## 5. Section `security` (Sandbox)

Options globales pour l'isolation des processus.

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `allowed_imports` | [Base] | Modules Python autorisés dans le Sandbox. |
| `forbidden_imports` | [Base] | Modules explicitement bannis (prioritaires). |
| `ipc.timeout` | `10.0` | Timeout maximal d'une réponse de plugin (sec). |

### Limites de Ressources (Défaut)
```yaml
security:
  default_limits:
    max_memory_mb: 128
    max_disk_mb: 50
    timeout_seconds: 10
    rate_limit:
      calls: 100
      period_seconds: 60
```

## 6. Section `marketplace` (Extensions)

```yaml
marketplace:
  url: "https://marketplace.xcore.dev"
  api_key: "${XCORE_MKT_KEY}"
  cache_ttl: 300
```
