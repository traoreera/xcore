# nosqlprovider.py

`xcore/integration/provider/nosqlprovider.py` est actuellement vide.

## Intention

Point d’extension pour providers NoSQL (MongoDB, Redis documents, etc.).

## Suggestion de structure

- `NoSQLProvider` (connect/close)
- `get_database(name)`
- `healthcheck()`

## Contribution

- Spécifier les capacités minimales attendues par le core.
- Ajouter des tests de robustesse sur gestion d’erreurs réseau.
