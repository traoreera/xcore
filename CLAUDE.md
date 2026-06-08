# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# CLAUDE.md — xcore

## Présentation

**xcore v2.3.0** — framework d'orchestration plugin-first construit sur FastAPI.
Charge, isole et gère des plugins modulaires dans un environnement sandboxé.

- **Language** : Python 3.12+
- **Framework** : FastAPI + uvicorn
- **Dépendances** : Poetry
- **Config** : `integration.yaml` (principal) — pas `xcore.yaml`
- **CLI** : `poetry run xcli`

---

## Commandes essentielles

```bash
# Démarrer l'API en dev
poetry run xcli worker start api

# Tests
make test                                                       # suite complète avec coverage
make test-cov                                                   # tests + rapport HTML de coverage
poetry run pytest tests/ -x -q                                  # rapide, stoppe au 1er échec
poetry run pytest tests/unit/kernel/test_supervisor.py -x -q   # fichier unique
poetry run pytest tests/ -k "test_boot" -x                     # filtrer par nom

# Lint & format
make lint-fix    # auto-corrige (black + isort)
make lint-check  # vérifie sans modifier (utilisé par CI)

# Build docs
poetry run mkdocs build
poetry run mkdocs serve          # preview local

# Sécurité
make auto-security               # Bandit scan
```

---

## Architecture clé

```
xcore/
├── kernel/
│   ├── api/           # contract.py (TrustedBase, BasePlugin), context.py (PluginContext)
│   ├── observability/ # logging.py (XcoreLogger), metrics.py, tracing.py, health.py
│   ├── runtime/       # lifecycle.py, loader.py, supervisor.py, activator.py
│   │                  # ephemeral_handler.py, warm_pool.py (pool d'instances préchauffées)
│   ├── tenancy/       # middleware.py, services.py (TenantAwareDB/Cache/Scheduler)
│   └── permissions/   # engine.py
├── services/
│   ├── scheduler/     # service.py — APScheduler + lock Redis distribué
│   ├── cache/         # service.py + backends/
│   └── database/      # manager.py + adapters/
├── configurations/    # loader.py, sections.py
└── sdk/               # base classes + décorateurs pour développeurs de plugins
```

**Flux d'un appel HTTP :**
```
HTTP → TenantMiddleware → Router → supervisor.call()
     → IPCAuthMiddleware → TracingMiddleware → RateLimitMiddleware
     → PermissionMiddleware → RetryMiddleware → _dispatch()
     → ContextVar tenant_id mis à jour → handler.call() → Plugin.handle()
```

---

## Conventions de code

### Logging — TOUJOURS utiliser get_logger (jamais logging.getLogger)

```python
from xcore.kernel.observability import get_logger
logger = get_logger("xcore.mon.module")

# Champs structurés en kwargs — jamais de f-strings dans les messages
logger.info("connexion établie", adapteur="db", type="postgresql")
logger.error("échec chargement", plugin="xlicense", erreur=str(e))
logger.debug("transition d'état", plugin="xlicense", de="loading", vers="ready")
```

### Observabilité dans un plugin

```python
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        # Propriétés directes sur TrustedBase — pas self.ctx.metrics
        self.logger.info("action reçue", action=action)
        self.metrics.counter("calls_total", labels={"plugin": "shop"}).inc()

        with self.tracer.span("process") as span:
            span.set_attribute("action", action)
            result = await self._process(payload)

        @self.health.register("shop.db")
        async def check():
            return await self.get_service("db").health_check()
```

### Scheduler — pattern _JOB_REGISTRY

Le scheduler utilise un registre module-level + dispatcher picklable pour contourner la limite de pickle de RedisJobStore. **Ne jamais passer de bound methods directement à `add_job`** — le service s'en charge automatiquement.

Les jobs sont sécurisés contre les doublons en multi-workers via un lock Redis (`xcore:sched:lock:<job_id>`).

### Multi-tenancy — ContextVar, pas mutation

Le tenant courant est stocké dans `_current_tenant_id: ContextVar[str]` dans `tenancy/services.py`. Les services `TenantAwareDB/Cache/Scheduler` lisent ce ContextVar dynamiquement à chaque opération.

**Ne jamais muter `instance.ctx.services` à chaque requête** — c'est une race condition. Le wrapping se fait UNE FOIS au `on_load` du plugin, et le ContextVar change par requête.

```python
# Dans supervisor._dispatch — correct
token = _current_tenant_id.set(tenant_id)
try:
    return await handler.call(action, payload)
finally:
    _current_tenant_id.reset(token)
```

---

## Configuration YAML (sections importantes)

```yaml
# integration.yaml
services:
  scheduler:
    enabled: true
    backend: redis      # "memory" | "redis"
    timezone: Europe/Paris
    url: redis://localhost:6379/1

observability:
  logging:
    level: DEBUG
    output: json        # "text" | "json" — LU par le loader (champ output)
    file: log/app.log
  metrics:
    backend: prometheus # "memory" | "prometheus"

tenancy:
  enabled: false        # true pour activer l'isolation multi-tenant
  isolate_db: true
  isolate_cache: true
  isolate_scheduler: false
```

---

## Développement de plugins

Structure minimale :
```
app/plugins/mon_plugin/
├── plugin.yaml   # manifest (name, version, execution_mode, permissions)
└── src/
    └── main.py   # class Plugin(TrustedBase)
```

```python
# src/main.py
from xcore import TrustedBase, ok, error
from xcore.sdk import cron, interval, health_check

class Plugin(TrustedBase):

    async def on_load(self):
        self.db = self.get_service("db")
        self.logger.info("plugin chargé")

    @cron("0 3 * * *")           # décorateur SDK — enregistré automatiquement
    async def nightly_cleanup(self):
        ...

    @health_check("mon_plugin.db")
    async def check_db(self) -> tuple[bool, str]:
        try:
            await self.db.execute("SELECT 1")
            return True, "ok"
        except Exception as e:
            return False, str(e)

    async def handle(self, action, payload):
        if action == "ping":
            return ok(msg="pong")
        return error("action inconnue")
```

---

## Tests

```
tests/
├── unit/           # tests sans I/O externe
├── integration/    # tests avec Redis + SQLite
├── fixtures/       # données partagées
├── conftest.py
└── pytest.ini      # asyncio_mode = auto
```

Variables d'environnement pour les tests :
```bash
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key
```

---

## CI/CD

| Workflow | Déclencheur | Ce qu'il fait |
|----------|-------------|---------------|
| `ci.yml` | push/PR sur `main`, `features` | lint (black+isort+flake8), mypy, tests+coverage |
| `pr.yml` | PR sur `main`, `features` | titre PR (conventional commits), taille PR, tests rapides |
| `docs.yml` | push sur `main` | build + deploy MkDocs sur GitHub Pages |
| `security.yml` | push + lundi 7h | pip-audit, bandit, gitleaks |
| `release.yml` | tag `v*.*.*` | tests, build wheel, GitHub Release |

Le cache `.venv` est clé sur `poetry.lock` — un changement de dépendances invalide automatiquement le cache.

---

## Pièges connus

- **`poetry add` en CI** — NE JAMAIS faire `poetry add` dans un workflow CI, ça mute `poetry.lock`. Utiliser `poetry run pip install <pkg> --quiet` à la place.
- **`make lint-check`** — le Makefile s'appelle `makefile` (minuscule), mais `make` le trouve sur Linux.
- **Dossiers `extensions/` et `plugins/`** — n'existent pas dans le repo racine. Ne pas les référencer dans les outils CI/bandit.
- **`logging.getLogger()`** — NE PAS utiliser. Toujours `get_logger()` de `xcore.kernel.observability`.
- **Branche principale** : `main`. Ne pas confondre avec les branches de feature (`add-ephemeral`, etc.).
- **Seuil de coverage** : `fail_under = 80` dans `pyproject.toml` (`branch = true`). Le CI échoue en dessous. Patcher les imports locaux dans `boot()` au niveau du module source (`xcore.services.container.ServiceContainer`) et non au niveau `xcore`.
- **`asyncio_mode = auto`** dans `pyproject.toml` — pas besoin de `@pytest.mark.asyncio` sur chaque test async.
