# Exemple : Plugin de Base (Basic Plugin)

Cet exemple présente la structure minimale d'un plugin XCore fonctionnel en mode `trusted`.

---

## 1. Structure du Répertoire

```text
basic_plugin/
├── plugin.yaml
└── src/
    └── main.py
```

---

## 2. Le Manifeste (`plugin.yaml`)

```yaml
name: basic_plugin
version: 1.0.0
author: XCore Team
description: Un plugin d'exemple minimaliste
execution_mode: trusted
entry_point: src/main.py

# Aucun service ou permission requis ici
```

---

## 3. Le Code Source (`src/main.py`)

```python
from xcore.sdk import TrustedBase, ok, error

class Plugin(TrustedBase):
    """
    Plugin de base démontrant l'implémentation de la méthode handle().
    """

    async def on_load(self) -> None:
        """Appelé lors du chargement initial."""
        print(f"✅ Plugin {self.ctx.name} v{self.ctx.version} chargé !")

    async def handle(self, action: str, payload: dict) -> dict:
        """
        Point d'entrée pour les appels IPC (Inter-Process Communication).
        """
        if action == "ping":
            return ok(message="pong")

        if action == "echo":
            # Retourne le payload reçu
            return ok(echo=payload)

        # En cas d'action inconnue, retourner une erreur standard
        return error(f"Action '{action}' inconnue", code="unknown_action")

    async def on_unload(self) -> None:
        """Appelé avant le déchargement."""
        print(f"👋 Plugin {self.ctx.name} déchargé.")
```

---

## 4. Test de l'Exemple

### Appel via cURL (IPC sur HTTP)

```bash
curl -X POST http://localhost:8082/plugin/ipc/basic_plugin/ping \
  -H "X-Plugin-Key: change-me-in-production" \
  -d '{"payload": {}}'

# Réponse :
# {"status":"ok","plugin":"basic_plugin","action":"ping","result":{"status":"ok","message":"pong"}}
```

---

## Ce que vous avez appris

✅ **Héritage** : Un plugin doit hériter de `TrustedBase`.
✅ **Points d'entrée** : `on_load`, `on_unload` et `handle`.
✅ **Helpers de réponse** : Utilisation de `ok()` et `error()`.
✅ **Isolation** : Même un plugin minimaliste est isolé par son propre namespace.
