# Configuration (`xcore.yaml`)

Le fichier `xcore.yaml` centralise toute la configuration du framework.

---

## Structure complète

```yaml
# ── Application ──────────────────────────────────────────────
app:
  name: "mon-app"
  env: development          # development | staging | production
  debug: false
  secret_key: "${APP_SECRET_KEY}"   # clé JWT / sessions
  plugin_prefix: "/plugin"          # préfixe des routes HTTP plugins
  plugin_tags: []                   # tags OpenAPI globaux
  server_key: "${SERVER_KEY}"       # clé HMAC pour l'API interne
  server_key_iterations: 100000

# ── Plugins ──────────────────────────────────────────────────
plugins:
  directory: ./plugins
  secret_key: "${PLUGIN_SECRET_KEY}"
  strict_trusted: true      # true = refus des plugins non signés
  interval: 2               # watcher hot-reload (secondes, 0 = désactivé)
  entry_point: src/main.py

  # Fichiers ignorés par le watcher
  snapshot:
    extensions: [".log", ".pyc", ".html", ".map"]
    filenames: ["__pycache__", "__init__.py", ".env", ".DS_Store"]
    hidden: true

# ── Services ─────────────────────────────────────────────────
services:
  # Bases de données (plusieurs connexions possibles)
  databases:
    db:                           # accessible via self.get_service("db")
      type: sqlasync              # sqlasync | sql | redis | mongodb
      url: "${DATABASE_URL}"
      pool_size: 5
      max_overflow: 10
      echo: false

    analytics:                    # accessible via self.get_service("analytics")
      type: sqlasync
      url: "${ANALYTICS_DB_URL}"

    redis_db:                     # accessible via self.get_service("redis_db")
      type: redis
      url: "${REDIS_URL}"
      max_connections: 50

  # Cache
  cache:
    backend: redis                # memory | redis
    url: "${REDIS_URL}"
    ttl: 300
    max_size: 10000               # ignoré en mode redis

  # Scheduler
  scheduler:
    enabled: true
    backend: redis                # memory | redis | database
    timezone: Europe/Paris

    # Jobs statiques (optionnel)
    jobs:
      - id: cleanup
        func: myapp.tasks:cleanup
        trigger: cron
        hour: 3
        minute: 0

  # Extensions (services custom)
  extensions:
    stripe:
      api_key: "${STRIPE_KEY}"

# ── Observabilité ─────────────────────────────────────────────
observability:
  logging:
    level: INFO                   # DEBUG | INFO | WARNING | ERROR
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: log/app.log
    max_bytes: 10485760           # 10 MB
    backup_count: 5

  metrics:
    enabled: true
    backend: memory               # memory | prometheus | statsd
    prefix: xcore

  tracing:
    enabled: false
    backend: noop                 # noop | opentelemetry | jaeger
    service_name: xcore
    endpoint: null

# ── Sécurité ─────────────────────────────────────────────────
security:
  # (Réservé — extension future pour Vault, rotation de clés, etc.)

# ── Marketplace ───────────────────────────────────────────────
marketplace:
  url: "https://marketplace.xcore.dev"
  api_key: "${MARKETPLACE_KEY}"
```

---

## Types de bases de données

| `type` | Driver | Usage |
|:-------|:-------|:------|
| `sqlasync` | SQLAlchemy + asyncpg / aiosqlite | PostgreSQL, MySQL, SQLite async |
| `sql` | SQLAlchemy synchrone | SQLAlchemy sync |
| `redis` | redis-py asyncio | Redis key/value |
| `mongodb` | Motor (async) | MongoDB |

---

## Résolution des valeurs

### Substitution `${VAR}`

Toute valeur au format `${NOM_VAR}` est substituée depuis l'environnement OS ou le `.env` configuré.

```yaml
app:
  secret_key: "${APP_SECRET_KEY}"   # résolu depuis os.environ
```

### Surcharge via variables d'environnement

Format : `XCORE__<SECTION>__<CLE>=valeur`

```bash
XCORE__APP__DEBUG=true
XCORE__APP__ENV=production
XCORE__SERVICES__CACHE__BACKEND=redis
XCORE__SERVICES__CACHE__URL=redis://prod-redis:6379/0
XCORE__PLUGINS__STRICT_TRUSTED=true
```

Priorité : **variables d'environnement > xcore.yaml > valeurs par défaut**

### Chargement d'un `.env`

```yaml
app:
  dotenv: "./.env"    # chemin relatif au projet
```

---

## Valeurs par défaut

Tous les champs ont des valeurs par défaut : un `xcore.yaml` vide (ou absent) ne provoque pas d'erreur, XCore démarre en mode minimal (SQLite en mémoire, cache memory, scheduler désactivé).

---

## Chemin du fichier de configuration

Pour éviter toute ambiguïté, il est recommandé de passer explicitement le chemin du fichier :

```python
xcore = Xcore(config_path="config/prod.yaml")
```

Ou via CLI :

```bash
poetry run xcore --config config/prod.yaml plugin list
```

Si aucun chemin n'est fourni, le `ConfigLoader` essaie des chemins de fallback historiques (`integation.yaml`, `integation.yml`, `integation.json`, `config/integation.yaml`).
