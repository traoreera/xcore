# __init__.py (xcore)

Le fichier `xcore/__init__.py` expose l’API publique minimale du package.

## Rôle

- Expose `Manager` pour l’orchestration plugins.
- Expose `BaseService` pour les extensions du framework d’intégration.
- Définit `__all__` pour stabiliser les imports publics.

## Exports

```python
from .integration.plugins.base import BaseService
from .manager import Manager

__all__ = ["BaseService", "Manager"]
```

## Exemple d’utilisation

```python
from xcore import Manager, BaseService
```

## Contribution

- Ajouter ici uniquement des exports stables.
- Éviter de réexporter des modules internes non matures.
- Garder ce fichier léger (pas de logique métier).
