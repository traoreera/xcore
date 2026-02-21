# Tests

xcore utilise `pytest` comme framework de test, avec `httpx` pour les tests d'intégration des routes FastAPI.

---

## Lancer les tests

```bash
# Tous les tests
make test

# Avec sortie détaillée
poetry run pytest -v

# Un fichier spécifique
poetry run pytest tests/test_plugins.py -v

# Un test spécifique
poetry run pytest tests/test_plugins.py::test_plugin_load -v

# Avec couverture de code
poetry run pytest --cov=xcore --cov-report=term-missing
poetry run pytest --cov=xcore --cov-report=html  # rapport HTML dans htmlcov/
```

---

## Structure des tests

```
tests/
├── conftest.py           ← fixtures partagées
├── test_core/
│   ├── test_loader.py    ← tests du PluginLoader
│   ├── test_validator.py ← tests du Validator
│   └── test_manager.py   ← tests du Manager
├── test_services/
│   ├── test_auth.py
│   ├── test_cache.py
│   └── test_database.py
├── test_plugins/
│   └── test_example_plugin.py
└── fixtures/
    └── fake_plugin/      ← plugin factice pour les tests
        ├── __init__.py
        └── run.py
```

---

## Fixtures communes (`conftest.py`)

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from main import app
from extensions.services.database import get_db, Base, engine

@pytest.fixture(scope="session")
def db():
    """Base de données de test en mémoire."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db):
    """Client HTTP de test."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers(client):
    """Headers avec token JWT d'un utilisateur de test."""
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def admin_headers(client):
    """Headers avec token JWT d'un admin de test."""
    response = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpassword"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

---

## Écrire des tests de routes

```python
# tests/test_plugins/test_todo_plugin.py
import pytest

def test_create_todo(client):
    response = client.post("/app/todo/", json={
        "title": "Mon premier todo",
        "priority": 2
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Mon premier todo"
    assert data["priority"] == 2
    assert data["done"] is False
    assert "id" in data

def test_create_todo_titre_vide(client):
    response = client.post("/app/todo/", json={"title": ""})
    assert response.status_code == 422  # Validation Pydantic

def test_get_todo_inexistant(client):
    response = client.get("/app/todo/99999")
    assert response.status_code == 404

def test_complete_todo(client):
    # Créer d'abord
    create_resp = client.post("/app/todo/", json={"title": "À faire"})
    todo_id = create_resp.json()["id"]
    
    # Marquer comme fait
    response = client.patch(f"/app/todo/{todo_id}/done")
    assert response.status_code == 200
    assert response.json()["done"] is True
```

---

## Tester le PluginLoader

```python
# tests/test_core/test_loader.py
import pytest
from manager.plManager.loader import PluginLoader
from manager.plManager.validator import PluginValidator

def test_charge_plugin_valide(tmp_path):
    """Un plugin conforme doit être chargé sans erreur."""
    # Créer un plugin factice
    plugin_dir = tmp_path / "fake_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "run.py").write_text("""
from fastapi import APIRouter, Request
PLUGIN_INFO = {
    "version": "1.0.0",
    "author": "test",
    "Api_prefix": "/app/fake",
    "tag_for_identified": ["fake"],
}
router = APIRouter(prefix="/fake", tags=["fake"])
class Plugin:
    def __init__(self):
        super().__init__()
""")
    
    validator = PluginValidator()
    result = validator.validate(str(plugin_dir))
    assert result.is_valid is True

def test_rejette_plugin_sans_plugin_info(tmp_path):
    """Un plugin sans PLUGIN_INFO doit être rejeté."""
    plugin_dir = tmp_path / "bad_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "run.py").write_text("""
from fastapi import APIRouter
router = APIRouter()
""")
    
    validator = PluginValidator()
    result = validator.validate(str(plugin_dir))
    assert result.is_valid is False
    assert "PLUGIN_INFO" in result.error
```

---

## Tests d'authentification

```python
# tests/test_services/test_auth.py

def test_login_succes(client):
    response = client.post("/auth/login", json={
        "email": "user@example.com",
        "password": "password"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_mauvais_mot_de_passe(client):
    response = client.post("/auth/login", json={
        "email": "user@example.com",
        "password": "mauvais"
    })
    assert response.status_code == 401

def test_route_protegee_sans_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401

def test_route_protegee_avec_token(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
```

---

## Bonnes pratiques

- Chaque test doit être **indépendant** — ne jamais supposer l'état laissé par un autre test.
- Utilisez des fixtures pour éviter la duplication.
- Testez les cas d'erreur autant que les cas de succès.
- Pour les plugins, testez les routes ET la logique métier séparément.
- Évitez les tests qui font des appels réseau réels — moquez les services externes avec `pytest-mock` ou `responses`.
