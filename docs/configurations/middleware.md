# middleware.py

Le fichier `middleware.py` définit la classe `MidlwareTypes`, responsable de la configuration des middlewares de l'API.

## Rôle

Ce fichier définit les types pour la configuration des middlewares de xcore, tels que les origines autorisées pour le CORS (Cross-Origin Resource Sharing).

## Définition du type `MidlwareTypes`

```python
from typing import TypedDict

class MidlwareTypes(TypedDict):
    origins: list[str]
```

- `origins`: Une liste de chaînes de caractères représentant les domaines autorisés à appeler l'API de xcore (ex: `["http://localhost:3000", "https://mon-app.com"]`).

## Utilisation

Importez ce type dans vos modules de configuration (par exemple, dans `Xcorecfg`) pour définir la structure de la section `midleware`.

### Exemple : Définition d'un middleware CORS

```python
from .middleware import MidlwareTypes
from typing import TypedDict

class MyCoreConfig(TypedDict):
    midleware: MidlwareTypes
```

## Contribution

- Si de nouveaux types de middleware sont ajoutés (ex: `RateLimiterTypes`, `AuthMiddlewareTypes`), leurs définitions de type doivent être ajoutées dans `middleware.py`.
- Assurez-vous que les types définis sont compatibles avec les bibliothèques de middleware utilisées par FastAPI (comme `CORSMiddleware`).
