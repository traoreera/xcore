# Module Integration Plugins

Ce module contient le runtime des extensions de services déclarées dans `integration.yaml`.

## Fichiers

```{toctree}
:maxdepth: 1

base
extension_loader
manager
```

## Contribution

- Favoriser `core/integration.py` comme point d’entrée canonique.
- Garder la compatibilité des signatures `name/config/env/registry` pour les services.
