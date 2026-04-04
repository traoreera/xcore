# Guide des Tests XCore

XCore a été conçu avec la testabilité comme priorité. Ce guide vous aide à tester vos plugins de manière robuste, tant en isolation qu'en intégration.

---

## 1. Philosophie des Tests

Dans XCore, les tests se répartissent en trois catégories :
1. **Tests de Plugins (Isolation)** : Tester la logique métier sans le framework.
2. **Tests d'Intégration (Noyau)** : Tester le chargement, les services et l'IPC.
3. **Tests de Sécurité (Sandbox)** : Vérifier que les restrictions de la sandbox sont bien appliquées.

---

## 2. Tester un Plugin en Isolation

Le moyen le plus simple est de tester la classe `Plugin` directement en mockant ses services.

```python
import pytest
from unittest.mock import MagicMock
from plugins.mon_plugin.src.main import Plugin

@pytest.mark.asyncio
async def test_mon_plugin_logic():
    # Instanciation manuelle
    p = Plugin()

    # Mock des services
    p.cache = MagicMock()
    p.cache.get.return_value = "ma_valeur"

    # Appel de l'action
    result = await p.handle("get_data", {"key": "test"})

    # Vérifications
    assert result["status"] == "ok"
    assert result["data"] == "ma_valeur"
```

---

## 3. Tester via le Framework (Intégration)

Utilisez le `Xcore` orchestrateur pour charger réellement vos plugins et tester les appels IPC réels.

```python
from xcore import Xcore
import pytest

@pytest.mark.asyncio
async def test_full_plugin_cycle():
    # Démarrage du framework (config par défaut)
    xcore = Xcore()
    await xcore.boot()

    # Appel IPC réel via le Supervisor
    result = await xcore.plugins.call("mon_plugin", "ping", {})

    # Vérifications
    assert result["status"] == "ok"
    assert result["msg"] == "pong"

    # Arrêt propre
    await xcore.shutdown()
```

---

## 4. Tester l'API HTTP (FastAPI)

Utilisez `TestClient` de FastAPI pour tester les endpoints HTTP exposés par vos plugins.

```python
from fastapi.testclient import TestClient
from app import app # Votre application FastAPI intégrant Xcore

client = TestClient(app)

def test_plugin_http_route():
    # Test de la route système IPC
    response = client.post(
        "/plugin/ipc/mon_plugin/action",
        headers={"X-Plugin-Key": "change-me-in-production"},
        json={"payload": {"key": "val"}}
    )
    assert response.status_code == 200

    # Test de la route REST du plugin
    response = client.get("/plugin/mon_plugin/status")
    assert response.status_code == 200
    assert response.json()["active"] is True
```

---

## 5. Exécution des Tests

Le projet utilise **Pytest**. Vous pouvez lancer tous les tests du framework et des plugins avec :

```bash
# Lancer tous les tests
poetry run pytest

# Lancer les tests d'un répertoire spécifique
poetry run pytest tests/unit/kernel/

# Voir la couverture de code
poetry run pytest --cov=xcore
```

---

## Bonnes Pratiques

1. **Utiliser des bases de données de test** : Configurez `DATABASE_URL` pour pointer vers une base SQLite en mémoire (`sqlite:///:memory:`) ou une base de test dédiée pour vos tests d'intégration.
2. **Nettoyage après test** : Assurez-vous de décharger les plugins (`unload`) après chaque test pour éviter les fuites de mémoire ou les conflits de namespace.
3. **Tester le mode Sandboxed** : Si votre plugin est destiné à être sandboxed, testez-le avec la commande `xcore sandbox run <name>` pour vérifier qu'aucune `PermissionError` n'est levée.
