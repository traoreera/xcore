# __init__.py (configurations)

Le fichier `xcore/configurations/__init__.py` est actuellement vide.

## Rôle

- Marquer `xcore/configurations` comme package Python.
- Préparer un point d’export futur pour les classes de configuration.

## Recommandation

Si vous voulez simplifier les imports, vous pouvez exporter explicitement:

```python
from .base import Configure, BaseCfg
from .core import Xcorecfg
```

## Contribution

- Si vous ajoutez des exports, garder une API claire et versionnée.
- Ne pas importer des modules lourds au chargement du package.
