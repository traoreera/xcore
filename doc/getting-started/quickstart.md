# Guide de Démarrage Rapide (5 min)

Apprenez à créer votre premier plugin XCore et à l'appeler via l'API.

## 1. Installation

Assurez-vous d'avoir Python 3.10+ et Poetry installés.

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
poetry install
```

## 2. Lancer le Serveur

```bash
poetry run uvicorn xcore.api.main:app --reload
```

Le serveur démarre par défaut sur `http://localhost:8000`.

## 3. Créer votre Premier Plugin

Créez un dossier pour votre plugin :
```bash
mkdir -p plugins/hello/src
```

### Le Manifeste (`plugins/hello/plugin.yaml`)
```yaml
name: hello
version: 1.0.0
execution_mode: trusted
entry_point: src/main.py
```

### Le Code (`plugins/hello/src/main.py`)
```python
from xcore.sdk import TrustedBase, action, route, ok

class HelloPlugin(TrustedBase):
    @action("greet")
    async def greet(self, payload: dict):
        name = payload.get("name", "Monde")
        return ok(message=f"Bonjour, {name} !")

    @route("/hello", method="GET")
    async def hello_world(self):
        return {"message": "Hello from XCore HTTP!"}
```

## 4. Tester le Plugin

Le plugin est chargé automatiquement s'il est dans le dossier `plugins/`.

### Test de l'Action (IPC via HTTP POST)
```bash
curl -X POST http://localhost:8000/app/hello/greet \
     -H "Content-Type: application/json" \
     -d '{"name": "Alice"}'
# Réponse : {"status": "ok", "message": "Bonjour, Alice !"}
```

### Test de la Route HTTP (FastAPI)
```bash
curl http://localhost:8000/plugins/hello/hello
# Réponse : {"message": "Hello from XCore HTTP!"}
```

## 5. Prochaines Étapes

- [Créer des plugins plus complexes](../guides/creating-plugins.md)
- [Utiliser les services (DB, Cache)](../guides/services.md)
- [Sécuriser avec le mode Sandbox](../guides/security.md)
