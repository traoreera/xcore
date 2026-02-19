# sqlprovider.py

`xcore/integration/provider/sqlprovider.py` est actuellement vide.

## Intention

Point d’extension prévu pour isoler les stratégies SQL (dialects, pool, transactions).

## Suggestion de structure

- `SQLProvider` (init/connect/dispose)
- `create_session()`
- `healthcheck()`

## Contribution

- Définir une interface provider avant implémentation.
- Ajouter des tests d’intégration SQLite/PostgreSQL/MySQL.
