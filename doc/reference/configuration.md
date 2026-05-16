# Configuration (`integration.yaml`)

Le fichier `integration.yaml` centralise toute la configuration du framework.

---

## Structure complète

```yaml
# ── Application ──────────────────────────────────────────────
app:
  name: "mon-app"
  env: development          # development | staging | production
  debug: false
  secret_key: "${APP_SECRET_KEY}"
  plugin_prefix: "/plugin"
  plugin_tags: []
  server_key: "${SERVER_KEY}"
  server_key_iterations: 100000

  # ── FastAPI ──────────────────────────────────────────────────
  fastapi:
    title: "Mon App"
    summary: "API propulsée par xcore"
    description: ""
    version: "1.0.0"
    debug: false
    docs_url: "/docs"
    redoc_url: "/redoc"
    openapi_url: "/openapi.json"
    redirect_slashes: true
    # terms_of_service: "https://example.com/terms"
    # contact:
    #   name: "Support"
    #   email: "support@example.com"
    # license_info:
    #   name: "MIT"
    deprecated: false

  # ── Uvicorn ──────────────────────────────────────────────────
  server:
    app: "main:app"
    host: "0.0.0.0"
    port: 8000
    workers: 1
    reload: false
    log_level: "info"
    proxy_headers: true
    forwarded_allow_ips: "*"

# ── Plugins ──────────────────────────────────────────────────
plugins:
  directory: ./plugins
  secret_key: "${PLUGIN_SECRET_KEY}"
  strict_trusted: true
  interval: 2
  entry_point: src/main.py

  snapshot:
    extensions: [".log", ".pyc", ".html", ".map"]
    filenames: ["__pycache__", "__init__.py", ".env", ".DS_Store"]
    hidden: true

# ── Services ─────────────────────────────────────────────────
services:
  databases:
    db:
      type: sqlasync
      url: "${DATABASE_URL}"
      pool_size: 5
      max_overflow: 10
      echo: false

    redis_db:
      type: redis
      url: "${REDIS_URL}"
      max_connections: 50

  cache:
    backend: redis            # memory | redis
    url: "${REDIS_URL}"
    ttl: 300
    max_size: 10000

  scheduler:
    enabled: true
    backend: redis
    timezone: Europe/Paris

  # ── Celery / XWorker ─────────────────────────────────────────
  xworker:
    enabled: true
    name: "mon-app"
    broker_url: "${REDIS_URL}"
    result_backend: "redis://localhost:6379/1"
    task_default_queue: default
    concurrency: 4
    task_soft_time_limit: 300
    task_time_limit: 360
    task_serializer: json
    result_serializer: json
    accept_content:
      - json
    result_expires: 86400
    broker_connection_retry_on_startup: true
    queues:
      - default
      - result
    modules: []               # modules Python contenant les @task()

  extensions:
    stripe:
      module: myapp.services.stripe:StripeService
      config:
        api_key: "${STRIPE_KEY}"

# ── Middlewares ───────────────────────────────────────────────
middleware:
  - name: timing
    module: xcore.kernel.api.middlewares.timing:RequestTimingMiddleware

  - name: cache_header
    module: xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware
    config:
      - name: header_prefix
        type: external
        value: "X-App"
      - name: cache_getter
        type: internal      # résolu via services.get("cache") à chaque requête
        value: cache

# ── Observabilité ─────────────────────────────────────────────
observability:
  logging:
    level: INFO
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: log/app.log
    max_bytes: 10485760
    backup_count: 5

  metrics:
    enabled: true
    backend: memory           # memory | prometheus | statsd
    prefix: xcore

  tracing:
    enabled: false
    backend: noop             # noop | opentelemetry | jaeger
    service_name: xcore
    endpoint: null

# ── Sécurité ─────────────────────────────────────────────────
security:
  allowed_imports:
    - fastapi
    - json
    - re
    - math
    - asyncio
    - logging
    - uuid
  forbidden_imports:
    - os
  rate_limit_default:
    calls: 200
    period_seconds: 60

# ── Multi-Tenancy ─────────────────────────────────────────────
tenancy:
  enabled: false             # true = active l'isolation par tenant
  header: "X-Tenant-ID"     # header HTTP lu pour identifier le tenant
  subdomain: false           # true = acme.monapp.com → tenant "acme"
  default_tenant: "default"  # utilisé si aucun header/subdomain trouvé
  isolate_cache: true        # préfixe les clés cache par tenant_id
  isolate_db: true           # SET search_path TO <tenant_id> (PostgreSQL)
  isolate_scheduler: false   # préfixe les job_id APScheduler par tenant_id
  enforce_ipc: true          # vérifie allowed_callers sur les appels IPC

# ── Marketplace ───────────────────────────────────────────────
marketplace:
  url: "https://marketplace.xcore.dev"
  api_key: "${MARKETPLACE_KEY}"
```

---

## Section `app`

### Champs principaux

| Champ | Type | Défaut | Description |
|:------|:-----|:-------|:------------|
| `name` | str | `"xcore-app"` | Nom de l'application |
| `env` | str | `"development"` | Environnement (`development` / `staging` / `production`) |
| `debug` | bool | `false` | Mode debug global |
| `secret_key` | str | — | Clé JWT / sessions (obligatoire en prod) |
| `plugin_prefix` | str | `"/plugin"` | Préfixe URL des routes plugins |
| `server_key` | str | — | Clé HMAC pour l'API interne |

### Sous-section `fastapi`

Configure le constructeur `FastAPI()`. Tous ces champs sont passés directement à FastAPI au démarrage.

| Champ | Type | Défaut | Description |
|:------|:-----|:-------|:------------|
| `title` | str | `"xcore"` | Titre affiché dans la doc Swagger |
| `summary` | str | `null` | Résumé court |
| `description` | str | `""` | Description longue (Markdown supporté) |
| `version` | str | `"0.1.0"` | Version de l'API |
| `docs_url` | str | `"/docs"` | URL Swagger UI (`null` pour désactiver) |
| `redoc_url` | str | `"/redoc"` | URL ReDoc (`null` pour désactiver) |
| `openapi_url` | str | `"/openapi.json"` | URL du schéma OpenAPI |
| `redirect_slashes` | bool | `true` | Redirection slash final |
| `terms_of_service` | str | `null` | URL CGU |
| `contact` | dict | `null` | Contact `{name, email, url}` |
| `license_info` | dict | `null` | Licence `{name, url}` |
| `deprecated` | bool | `false` | Marque l'API comme dépréciée |

### Sous-section `server`

Configure uvicorn pour `xcore worker start api`.

| Champ | Type | Défaut | Description |
|:------|:-----|:-------|:------------|
| `app` | str | `"main:app"` | Chemin de l'app ASGI |
| `host` | str | `"0.0.0.0"` | Adresse d'écoute |
| `port` | int | `8000` | Port |
| `workers` | int | `1` | Nombre de workers uvicorn |
| `reload` | bool | `false` | Auto-reload (dev uniquement) |
| `log_level` | str | `"info"` | Niveau de log uvicorn |
| `proxy_headers` | bool | `true` | Confiance aux headers `X-Forwarded-*` |
| `forwarded_allow_ips` | str | `"*"` | IPs autorisées pour les headers proxy |

---

## Section `services.xworker`

Intégration native de Celery dans le `ServiceContainer`.

| Champ | Type | Défaut | Description |
|:------|:-----|:-------|:------------|
| `enabled` | bool | `false` | Active le service |
| `name` | str | `"App"` | Nom de l'app Celery (logs, Flower) |
| `broker_url` | str | Redis local | URL du broker |
| `result_backend` | str | Redis local | URL du backend de résultats |
| `task_default_queue` | str | `"default"` | File par défaut |
| `concurrency` | int | `4` | Workers Celery (surchargeable via `-c`) |
| `task_soft_time_limit` | int | `300` | Secondes avant `SoftTimeLimitExceeded` |
| `task_time_limit` | int | `360` | Secondes avant kill forcé |
| `queues` | list | `["default"]` | Files d'attente déclarées |
| `modules` | list | `[]` | Modules Python contenant les `@task()` |
| `result_expires` | int | `86400` | Conservation des résultats (secondes) |

Accès depuis un plugin :

```python
worker = self.get_service("worker")    # → WorkerService
worker.send("tasks.send_email", user_id=42, queue="emails")
result = worker.get_result(task_id)
```

---

## Section `middleware`

Déclare les middlewares ASGI chargés automatiquement au démarrage.

```yaml
middleware:
  - name: mon_middleware
    module: myapp.middlewares.auth:AuthMiddleware
    config:
      - name: secret
        type: external        # valeur directe
        value: "${JWT_SECRET}"
      - name: cache_getter
        type: internal        # callable () → service, résolu à chaque requête
        value: cache
```

| Champ | Description |
|:------|:------------|
| `name` | Identifiant du middleware (logs) |
| `module` | Chemin Python `package.module:ClassName` |
| `config` | Liste de paramètres (voir ci-dessous) |

### Paramètres (`config`)

| Champ | Valeurs | Description |
|:------|:--------|:------------|
| `name` | str | Nom du paramètre dans le constructeur |
| `type` | `external` / `internal` | `external` = valeur directe ; `internal` = service résolu paresseusement |
| `value` | any | Valeur ou clé du service (ex: `"cache"`, `"db"`) |

> **Important** : les params `internal` reçoivent un callable `() → service` dans le constructeur, pas l'instance directe. Appeler `my_param()` à l'intérieur de `dispatch()` pour obtenir le service.

### Middlewares intégrés

| Module | Description |
|:-------|:------------|
| `xcore.kernel.api.middlewares.timing:RequestTimingMiddleware` | Ajoute `X-Process-Time` à chaque réponse |
| `xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware` | Ajoute des headers de diagnostic cache |

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

```yaml
app:
  secret_key: "${APP_SECRET_KEY}"
```

### Surcharge via variables d'environnement

Format : `XCORE__<SECTION>__<CLE>=valeur`

```bash
XCORE__APP__DEBUG=true
XCORE__APP__ENV=production
XCORE__SERVICES__CACHE__BACKEND=redis
XCORE__SERVICES__XWORKER__CONCURRENCY=8
```

Priorité : **variables d'environnement > integration.yaml > valeurs par défaut**

### Chargement d'un `.env`

```yaml
app:
  dotenv: "./.env"
```

---

## Section `tenancy`

Active et configure le système multi-tenant.

| Champ | Type | Défaut | Description |
|:------|:-----|:-------|:------------|
| `enabled` | bool | `false` | Active l'isolation par tenant. `false` = mode mono-tenant, `default_tenant` injecté partout. |
| `header` | string | `"X-Tenant-ID"` | Nom du header HTTP lu pour identifier le tenant. |
| `subdomain` | bool | `false` | Extrait le tenant depuis le sous-domaine (`acme.monapp.com` → `"acme"`). |
| `default_tenant` | string | `"default"` | Tenant utilisé si aucun header / sous-domaine trouvé. |
| `isolate_cache` | bool | `true` | Préfixe toutes les clés cache par `{tenant_id}:`. |
| `isolate_db` | bool | `true` | Exécute `SET search_path TO {tenant_id}, public` avant chaque requête (PostgreSQL). |
| `isolate_scheduler` | bool | `false` | Préfixe les `job_id` APScheduler par `{tenant_id}:`. |
| `enforce_ipc` | bool | `true` | Vérifie `allowed_callers` dans `plugin.yaml` sur chaque appel IPC. `false` = tout IPC autorisé. |

Voir [Guide Multi-Tenancy](../guides/tenancy.md) pour les exemples complets.

---

## Valeurs par défaut

Tous les champs ont des valeurs par défaut : un fichier absent ou vide ne provoque pas d'erreur — xcore démarre en mode minimal.
