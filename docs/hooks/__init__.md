# __init__.py (hooks)

Le fichier `xcore/hooks/__init__.py` centralise les exports du système de hooks.

## Rôle

- Expose `HookManager`, `Event`, `HookResult` et exceptions principales.
- Documente le module via docstring.

## API exportée

- `HookManager`
- `Event`
- `HookError`
- `HookTimeoutError`
- `HookResult`

## Exemple

```python
from xcore.hooks import HookManager, Event

hooks = HookManager()
```

## Contribution

- Toute nouvelle classe publique du hook system doit être exportée ici.
- Garder `__all__` synchronisé avec la vraie API supportée.
