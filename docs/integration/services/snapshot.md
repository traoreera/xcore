# snapshot.py (SnapshotService)

Le fichier `xcore/integration/services/snapshot.py` calcule des snapshots de dossiers et détecte les changements.

## Rôle

- Créer un hash par fichier
- Ignorer fichiers/extensions configurés
- Comparer `old` vs `new` via `diff`

## API

- `create(directory)`
- `diff(old, new)`
- `has_changed(old, new)`

## Exemple

```python
snap = SnapshotService(config)
before = snap.create("plugins")
# ... modifications ...
after = snap.create("plugins")
changes = snap.diff(before, after)
```

## Contribution

- Préserver les performances sur gros arborescences (I/O et hashing).
- Éviter de lever des exceptions bloquantes sur un fichier illisible isolé.
