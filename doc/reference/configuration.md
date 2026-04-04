# Configuration XCore (`xcore.yaml`)

Le fichier `xcore.yaml` est le cerveau du framework. Il centralise toutes les configurations de l'application, des services et des plugins.

---

## 1. Structure Globale

```yaml
app:
  name: "mon-app-xcore"
  env: "development" # development | staging | production
  debug: false
  secret_key: "change-me-in-production"
  plugin_prefix: "/plugin" # Préfixe racine des routes HTTP
  plugin_tags: ["XCore"] # Tags OpenAPI globaux

plugins:
  directory: "./plugins" # Répertoire de stockage des plugins
  secret_key: "change-me-in-production"
  strict_trusted: true # Refuse les plugins non signés en production
  interval: 2 # Intervalle du watcher en secondes
  entry_point: "src/main.py" # Point d'entrée par défaut

services:
  # Configuration des bases de données SQL/NoSQL
  databases:
    default:
      type: "sqlite" # sqlite | postgresql | mysql
      url: "sqlite:///./xcore.db"
      pool_size: 5
      max_overflow: 10
      echo: false

  # Configuration du cache (Mémoire ou Redis)
  cache:
    backend: "memory" # memory | redis
    ttl: 300
    max_size: 1000
    url: "redis://localhost:6379/0" # Requis si backend=redis

  # Configuration du planificateur de tâches
  scheduler:
    enabled: true
    backend: "memory" # memory | redis | database
    timezone: "UTC"

  # Extensions (Services personnalisés tiers)
  extensions:
    mon_service_custom:
      api_key: "${CUSTOM_API_KEY}"
      timeout: 30

observability:
  logging:
    level: "INFO" # DEBUG, INFO, WARNING, ERROR
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: "logs/xcore.log"

  metrics:
    enabled: false
    backend: "memory" # memory | prometheus | statsd
    prefix: "xcore"

  tracing:
    enabled: false
    backend: "noop" # noop | opentelemetry | jaeger
    service_name: "xcore"

security:
  allowed_imports: ["math", "json", "time"] # Imports autorisés en sandbox
  forbidden_imports: ["os", "sys", "subprocess"] # Imports bloqués par l'AST
  rate_limit_default:
    calls: 100
    period_seconds: 60

marketplace:
  url: "https://marketplace.xcore.dev"
  api_key: ""
  timeout: 10
  cache_ttl: 300
```

---

## 2. Variables d'Environnement (Interpolation)

XCore supporte l'injection de variables d'environnement directement dans le fichier YAML via la syntaxe `${VAR_NAME}`.

```yaml
app:
  secret_key: "${APP_SECRET_KEY}"
```

### Surcharge par variables d'environnement

Toutes les clés du fichier YAML peuvent être surchargées via des variables d'environnement préfixées par `XCORE__` (double soulignement pour les niveaux d'imbrication).

- `XCORE__APP__ENV=production` surcharge `app.env`.
- `XCORE__SERVICES__CACHE__BACKEND=redis` surcharge `services.cache.backend`.

---

## 3. Valeurs par Défaut

XCore est conçu pour fonctionner sans configuration (Zéro-Config) en utilisant des valeurs par défaut sécurisées :
- **DB** : SQLite locale (`./xcore.db`).
- **Cache** : En mémoire (`memory`).
- **Logs** : Niveau `INFO` vers la sortie standard.
- **Plugins** : Dossier `./plugins`.
