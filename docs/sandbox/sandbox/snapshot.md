# snapshot.py

Le fichier `xcore/sandbox/sandbox/snapshot.py` calcule des snapshots de dossier plugin et détecte les modifications.

## Rôle

- Intègre la config snapshot via `ManagerCfg(Configure())`
- Compare deux états: ajout/suppression/modification
- Garde un snapshot interne via `__call__`

## API

- `create(directory)`
- `diff(old, new)`
- `has_changed(old, new)`
- `__call__(directory)`

## Contribution

- Éviter les couplages globaux forts au chargement module.
- Conserver la tolérance aux erreurs de hashing/fichiers.
