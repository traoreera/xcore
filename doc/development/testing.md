# Guide des Tests

---

## Structure des tests

```
tests/
├── conftest.py                    # Fixtures globales
├── pytest.ini                     # Configuration pytest
├── unit/
│   ├── kernel/
│   │   ├── test_contract.py      # TrustedBase, BasePlugin, ok/error
│   │   └── test_events.py        # EventBus, HookManager
│   ├── services/
│   │   └── test_cache.py         # CacheService, MemoryBackend, RedisBackend
│   ├── plugins/
│   │   ├── test_base.py          # PluginManifest, PluginDependency
│   │   └── test_decorators.py    # @action, @validate_payload, @route
│   ├── security/
│   │   └── test_validation.py    # ManifestValidator, ASTScanner
│   └── test_configuration.py     # ConfigLoader, sections
└── integration/
    ├── test_xcore.py             # boot/shutdown complet
    └── test_plugin_lifecycle.py  # load/call/reload/unload
```

---

## Lancer les tests

```bash
# Suite complète
poetry run pytest

# Avec couverture
poetry run pytest --cov=xcore --cov-report=term-missing

# Par marker
poetry run pytest -m unit
poetry run pytest -m integration
poetry run pytest -m "not slow"

# Un test spécifique
poetry run pytest -k "test_permission_engine"

# Un fichier
poetry run pytest tests/unit/kernel/test_events.py

# Un répertoire
poetry run pytest tests/unit/kernel/

# Verbose avec traceback court
poetry run pytest -v --tb=short
```

**Markers disponibles :** `unit`, `integration`, `slow`, `skip_ci`

---

## Tester un plugin en isolation

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from plugins.mon_plugin.src.main import Plugin

@pytest.mark.asyncio
async def test_greet_action():
    plugin = Plugin()

    # Mock du contexte et des services
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    plugin.ctx = MagicMock()
    plugin.ctx.get_service.return_value = mock_cache

    await plugin.on_load()

    result = await plugin.handle("greet", {"name": "Alice"})
    assert result["status"] == "ok"
    assert "Alice" in result["message"]

    # Vérifier que le cache a été écrit
    mock_cache.set.assert_called_once()
```

---

## Tester via le framework (intégration)

```python
import pytest
from xcore import Xcore

@pytest.fixture
async def xcore_instance():
    xcore = Xcore(config_path="tests/fixtures/xcore_test.yaml")
    await xcore.boot()
    yield xcore
    await xcore.shutdown()

@pytest.mark.asyncio
async def test_plugin_call(xcore_instance):
    result = await xcore_instance.plugins.call("mon_plugin", "ping", {})
    assert result["status"] == "ok"

@pytest.mark.asyncio
async def test_plugin_reload(xcore_instance):
    await xcore_instance.plugins.reload("mon_plugin")
    result = await xcore_instance.plugins.call("mon_plugin", "ping", {})
    assert result["status"] == "ok"
```

---

## Tester l'API HTTP

```python
from fastapi.testclient import TestClient
from main import app  # votre application FastAPI

client = TestClient(app)

def test_plugin_route():
    response = client.post(
        "/plugin/mon_plugin/action",
        headers={"X-Plugin-Key": "test-key"},
        json={"action": "greet", "payload": {"name": "Test"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_protected_route():
    # Sans token → 401
    r = client.get("/plugin/mon_plugin/items")
    assert r.status_code == 401

    # Avec token valide
    r = client.get(
        "/plugin/mon_plugin/items",
        headers={"Authorization": "Bearer valid_token"},
    )
    assert r.status_code == 200
```

---

## Tester les événements

```python
import pytest
from xcore.kernel.events.bus import EventBus

@pytest.mark.asyncio
async def test_event_received():
    bus = EventBus()
    received = []

    @bus.on("user.created")
    async def handler(event):
        received.append(event.data)

    await bus.emit("user.created", {"email": "test@example.com"})

    assert len(received) == 1
    assert received[0]["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_wildcard_event():
    bus = EventBus()
    received = []

    @bus.on("order.*")
    async def catch_all(event):
        received.append(event.name)

    await bus.emit("order.created", {})
    await bus.emit("order.paid", {})
    await bus.emit("user.created", {})  # ne doit pas déclencher

    assert received == ["order.created", "order.paid"]
```

---

## Benchmarks

XCore embarque des benchmarks dans `tests/benchmarks/` via `pytest-benchmark`.

```bash
# Benchmarks kernel (permission engine, policy matching)
poetry run pytest tests/benchmarks/test_kernel_benchmarks.py \
                  tests/benchmarks/test_permission_bench.py \
                  --benchmark-only -v

# Exporter les résultats pour comparaison historique
poetry run pytest tests/benchmarks/ --benchmark-only \
                  --benchmark-json=bench_$(date +%Y%m%d).json

# Benchmarks cache (batch vs séquentiel)
poetry run python tests/benchmarks/cache_batch_perf.py
```

Résultats de référence : voir [Benchmarks](../reference/benchmarks.md).

---

## Bonnes pratiques

- Utiliser SQLite en mémoire pour les tests d'intégration : `url: "sqlite+aiosqlite:///:memory:"`.
- Toujours appeler `shutdown()` après `boot()` (utiliser une fixture `yield`).
- Pour les plugins sandboxed, tester avec `execution_mode: trusted` en tests unitaires, puis valider le sandbox avec `xcore sandbox run`.
- `asyncio_mode = auto` est activé — les tests `async def` sont automatiquement reconnus sans `@pytest.mark.asyncio` explicite.
