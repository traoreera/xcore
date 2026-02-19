# errorlanding.py

Le fichier `xcore/sandbox/tools/errorlanding.py` fournit un wrapper d’erreurs et un modèle de réponse.

## Éléments

- `ExceptionResponse` (Pydantic)
- classe `Error`
  - `exception_handler` (décorateur)
  - `Exception_Response(msg, type, extension)`

## Rôle

- Uniformiser les erreurs (`info`, `warning`, `error`)
- Logger durée d’exécution + exceptions

## Contribution

- Conserver la compatibilité des champs de `ExceptionResponse`.
- Éviter les side-effects dans le décorateur hors logging/normalisation.
