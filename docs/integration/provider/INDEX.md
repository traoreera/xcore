# Module Integration Provider

Ce module est réservé aux providers de persistance spécialisés.

## Fichiers

```{toctree}
:maxdepth: 1

sqlprovider
nosqlprovider
```

## État actuel

Les fichiers source sont vides pour le moment et servent de points d’extension.

## Contribution

- Ajouter des providers derrière une interface claire.
- Éviter d’y dupliquer la logique déjà présente dans `services/database.py`.
