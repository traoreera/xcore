# Guide de Test

Ce guide explique comment tester vos plugins et votre application XCore pour garantir une fiabilité maximale.

## Configuration de l'Environnement de Test

### Dépendances de test
Assurez-vous d'avoir installé les outils nécessaires :
```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

### Configuration Pytest
Créez un fichier `pytest.ini` à la racine pour configurer le mode asynchrone :
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

## Tester un Plugin (Mode Trusted)

Pour tester un plugin, vous pouvez l'instancier manuellement et simuler les appels de services.

### Exemple de test unitaire
```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from plugins.mon_plugin.src.main import Plugin

@pytest.mark.asyncio
async def test_action_dire_bonjour():
    # 1. Préparation (Setup)
    plugin = Plugin()
    plugin.ctx = MagicMock()

    # 2. Exécution (Execution)
    payload = {"nom": "Jules"}
    result = await plugin.handle("dire_bonjour", payload)

    # 3. Vérification (Assertion)
    assert result["status"] == "ok"
    assert "Jules" in result["message"]
```

## Tests d'Intégration avec XCore

Pour des tests plus réalistes, démarrez une instance minimale du framework.

```python
from xcore import Xcore

@pytest.fixture
async def app():
    xcore = Xcore(config_path="tests/xcore.test.yaml")
    await xcore.boot()
    yield xcore
    await xcore.shutdown()

@pytest.mark.asyncio
async def test_workflow_complet(app):
    # Appel via le supervisor (inclut les middlewares)
    result = await app.plugins.call("mon_plugin", "faire_calcul", {"a": 10, "b": 5})
    assert result["total"] == 15
```

## Tester les Routes HTTP

Utilisez `httpx` pour simuler des requêtes vers les endpoints exposés par vos plugins.

```python
from httpx import AsyncClient
from app import app # Votre instance FastAPI

@pytest.mark.asyncio
async def test_endpoint_http():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/plugins/mon_plugin/statut")

    assert response.status_code == 200
    assert response.json()["etat"] == "actif"
```

## Tester en Mode Sandbox

Le test des plugins sandboxés est crucial car ils subissent des restrictions strictes.

```python
@pytest.mark.asyncio
async def test_sandbox_security(app):
    # Tenter une action interdite (ex: accès au disque hors data/)
    result = await app.plugins.call("plugin_tiers", "lire_config_systeme", {})

    # Doit être intercepté par le FilesystemGuard
    assert result["status"] == "error"
    assert result["code"] == "filesystem_denied"
```

## Simulation de Services (Mocking)

Il est souvent préférable de ne pas utiliser de vraie base de données ou de vrai Redis pendant les tests unitaires.

```python
@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get.return_value = "valeur_cachee"
    return cache

@pytest.mark.asyncio
async def test_avec_mock(mock_cache):
    plugin = Plugin()
    # Injection du mock dans le plugin
    plugin.get_service = MagicMock(return_value=mock_cache)

    result = await plugin.handle("get_data", {"key": "test"})
    assert result["data"] == "valeur_cachee"
```

## Bonnes Pratiques de Test

1. **Isolation** : Chaque test doit être indépendant des autres. Utilisez des fixtures pour réinitialiser l'état.
2. **Couverture** : Visez au moins 80% de couverture de code pour les plugins critiques.
   ```bash
   pytest --cov=plugins/mon_plugin
   ```
3. **Edge Cases** : Testez les payloads vides, les types de données incorrects et les erreurs de services.
4. **Performance** : Surveillez le temps d'exécution de vos tests. Un test unitaire ne devrait pas dépasser quelques millisecondes.
