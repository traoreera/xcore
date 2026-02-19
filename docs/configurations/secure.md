# secure.py

Le fichier `secure.py` définit la classe `Secure`, responsable de la configuration de la sécurité.

## Rôle

La classe `Secure` cible la section `"secure"` du fichier `config.json`. Elle gère des paramètres essentiels pour le bon fonctionnement de la sécurité :
- Les algorithmes de hachage de mot de passe et leurs schémas.
- Le chemin vers le fichier d'environnement (.env).

## Structure de `Secure`

```python
class Secure(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "secure")
        ...
```

### Paramètres `default_migration` (SecureTypes)

Si la section n'est pas présente dans le fichier JSON, les valeurs suivantes sont utilisées :
- `password`: `{"algorithms": ["bcrypt"], "scheme": "bcrypt", "category": "password"}`
- `dotenv`: `./security/.env`

## Exemple d'utilisation

```python
from xcore.configurations.secure import Secure
from xcore.configurations.base import Configure

# Initialisation
secure_cfg = Secure(conf=Configure())

# Accès aux algorithmes de mot de passe
algorithms = secure_cfg.custom_config["password"]["algorithms"]

# Accès au chemin du fichier d'environnement
dotenv_path = secure_cfg.custom_config["dotenv"]
```

## Détails Techniques

- `SecureTypes`: Un `TypedDict` qui définit la structure complexe de la configuration de la sécurité.
- `PasswordType`: Un `TypedDict` pour configurer les paramètres de hachage de mot de passe.
- `custom_config`: Cette propriété contient le dictionnaire de configuration final pour la sécurité.

## Contribution

- Pour ajouter un nouvel algorithme de hachage de mot de passe par défaut, modifiez la liste `algorithms` dans le constructeur de `Secure`.
- Si vous modifiez le chemin vers le fichier d'environnement (`dotenv`), assurez-vous que les nouvelles valeurs sont compatibles avec les bibliothèques de sécurité utilisées par xcore.
