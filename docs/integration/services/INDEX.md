# Module Integration Services

Le module **Integration Services** contient les implémentations concrètes des services d'infrastructure de xcore.

## Fichiers

```{toctree}
:maxdepth: 1

database
cache
scheduler
snapshot
```

## Contribution

- Chaque service doit être indépendant et ne pas dépendre directement d'un autre (utilisez le `ServiceRegistry` ou le `EventBus` si nécessaire).
- Assurez-vous que les dépendances optionnelles (ex: `redis-py`, `apscheduler`, `sqlalchemy`) sont gérées avec des blocs `try-except ImportError`.
- Documentez l'API publique de chaque service.
