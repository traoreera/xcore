# base_plugin.py

Le fichier `xcore/sandbox/contracts/base_plugin.py` définit le contrat runtime plugin.

## Contenu

- `BasePlugin` (`Protocol`)
- `TrustedBase` (`ABC` optionnelle)
- Helpers `ok()` et `error()`

## Contrat minimal

```python
async def handle(self, action: str, payload: dict) -> dict
```

## Trusted

`TrustedBase` ajoute:

- `get_service(name)`
- hooks de cycle de vie: `on_load`, `on_unload`, `on_reload`
- hook `env_variable(manifest_env)`

## Exemple

```python
from xcore.sandbox.contracts.base_plugin import TrustedBase, ok

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        if action == "ping":
            return ok({"pong": True})
        return {"status": "error", "msg": "unknown action"}
```

## Contribution

- Garder le contrat simple et stable pour les auteurs plugins.
- Éviter les dépendances lourdes dans ce fichier de contrat.
