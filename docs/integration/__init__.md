# __init__.py (integration)

Le fichier `xcore/integration/__init__.py` expose le framework d’intégration (v2.0.0).

## Rôle

- Fournir un point d’entrée unique (`Integration`, config, registry, event bus).
- Exposer des helpers (`get_config`, `reload_config`, `get_event_bus`, `get_registry`).

## Exports clés

- `Integration`
- `IntegrationConfig`
- `EventBus`, `Event`
- `ServiceRegistry`, `ServiceScope`

## Exemple

```python
from xcore.integration import Integration

integration = Integration("integration.yaml")
await integration.init()
```

## Contribution

- Ne conserver ici que des APIs stables de haut niveau.
- Éviter d’exposer des classes internes/privées.
