# manager.py (integration/plugins)

Le fichier `xcore/integration/plugins/manager.py` contient une implémentation de `Integration` très proche de `xcore/integration/core/integration.py`.

## Rôle

- Orchestrer config, registry, DB, cache, scheduler et extensions.
- Fournir `init()`, `shutdown()`, `status()` et accès aux services.

## Point d’attention

Ce fichier duplique fortement la logique de `core/integration.py`.

## Recommandation

- Utiliser un seul orchestrateur canonique pour limiter les divergences.
- Si les deux sont conservés, maintenir des tests de non-régression sur les deux chemins.

## Exemple

```python
from xcore.integration.plugins.manager import Integration

integration = Integration("integration.yaml")
await integration.init()
```

## Contribution

- Éviter les changements sur une seule version sans reporter sur l’autre.
- Documenter explicitement la stratégie de déduplication/refactor.
