# deps.py

Le fichier `deps.py` définit les structures de données typées (`TypedDict`) partagées par plusieurs modules de configuration dans xcore.

## Rôle

Ce fichier sert de point central pour la définition des types complexes utilisés dans le fichier `config.json`. Son utilisation permet de bénéficier de l'auto-complétion et du typage statique lors de la manipulation de la configuration.

## Définitions de types

### `Logger`

Définit la configuration standard pour la journalisation.

```python
from typing import TypedDict

class Logger(TypedDict):
    console: bool
    file: str
```

- `console`: Active/désactive l'affichage des logs dans la console.
- `file`: Chemin vers le fichier de stockage des logs.

## Utilisation

Importez ces types dans vos modules de configuration pour définir la structure des sections attendues.

### Exemple : Définition d'un TypedDict

```python
from .deps import Logger
from typing import TypedDict

class MyConfig(TypedDict):
    url: str
    log: Logger
```

## Contribution

- Si un type de configuration est utilisé dans plus d'un module (par exemple, le format des paramètres de logs), il doit être défini dans `deps.py`.
- Si un type est spécifique à un seul module de configuration, il est préférable de le définir directement dans le fichier du module pour éviter de surcharger `deps.py`.
- Ne mettez que des `TypedDict` ou des constantes simples dans ce fichier pour éviter les dépendances circulaires.
