# manager.py (PluginManager)

Le fichier `xcore/sandbox/manager.py` contient l’orchestrateur principal des plugins.

## Responsabilités

- Chargement de tous les manifestes
- Tri topologique des dépendances (`requires`)
- Activation par mode (`trusted`, `sandboxed`, `legacy`)
- Appel plugin (`call`) avec `rate limit` + `retry/backoff`
- Administration dynamique (`load`, `unload`, `reload`)
- Arrêt propre (`shutdown`)

## API principale

- `load_all()`
- `call(plugin_name, action, payload)`
- `load(plugin_name)`
- `unload(plugin_name)`
- `reload(plugin_name)`
- `shutdown(timeout=10.0)`
- `status()`

## Détails importants

- `load_all()` charge par vagues parallèles après tri topo.
- Trusted: scan AST non bloquant (warning).
- Sandboxed: scan AST bloquant.
- Peut auto-attacher des routeurs FastAPI pour plugins trusted.

## Exemple

```python
pm = PluginManager("plugins", secret_key=b"...", services={"db": db})
await pm.load_all()
res = await pm.call("erp_core", "ping", {})
```

## Contribution

- Toute nouvelle fonctionnalité doit préserver l’idempotence de `load/reload/unload`.
- Vérifier les échecs en cascade sur dépendances (`requires`).
