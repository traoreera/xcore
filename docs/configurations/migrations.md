# migrations.py

Le fichier `migrations.py` définit la classe `Migration`, responsable de la configuration du système de migrations de base de données (Alembic).

## Rôle

La classe `Migration` cible la section `"migration"` (nom historique) du fichier `config.json`. Elle gère des paramètres essentiels pour le bon fonctionnement des migrations :
- L'URL de connexion à la base de données.
- La configuration de l'auto-découverte des modèles et des plugins.
- Les paramètres de sauvegarde (backup) avant migration.
- Les motifs d'exclusion lors de la génération de modèles.

## Structure de `Migration`

```python
class Migration(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "migration")
        ...
```

### Paramètres `default_migration` (MigrationTypes)

Si la section n'est pas présente dans le fichier JSON, les valeurs suivantes sont utilisées :
- `url`: `sqlite:///test.db`
- `alembic_config`: `alembic.ini`
- `auto_discover_models`: `True`
- `automigration`: `{"models": ["./auth", "./manager/models/", "./admin/", "./otpProvider"], "plugins": ["./plugins"]}`
- `explusion_patern`: Contient une liste de répertoires (`__pycache__`, `.git`, etc.) et de motifs de fichiers (`__init__.py`, `test_*.py`, etc.) à exclure lors de la découverte des modèles.
- `backup`: `{"auto_backup_before_migration": True, "backup_directory": "./backups", "max_backup_files": 5, "backup_name_format": "backup_%Y%m%d_%H%M%S.sql"}`

## Exemple d'utilisation

```python
from xcore.configurations.migrations import Migration
from xcore.configurations.base import Configure

# Initialisation
migration_cfg = Migration(conf=Configure())

# Accès à l'URL de connexion
db_url = migration_cfg.custom_config["url"]

# Accès à la configuration de sauvegarde
backup_enabled = migration_cfg.custom_config["backup"]["auto_backup_before_migration"]
```

## Détails Techniques

- `MigrationTypes`: Un `TypedDict` qui définit la structure complexe de la configuration des migrations.
- `AutoMigrationTypes`: Un `TypedDict` pour configurer l'auto-découverte des modèles et des plugins.
- `Backup`: Un `TypedDict` pour configurer le système de sauvegarde automatique.
- `ExclusionTypes`: Un `TypedDict` pour configurer les motifs d'exclusion lors de la découverte des modèles.

## Contribution

- Pour ajouter un nouveau répertoire à explorer pour les modèles lors des migrations, modifiez la liste `automigration` dans le constructeur de `Migration`.
- Si vous modifiez le format de nom des sauvegardes (`backup_name_format`), assurez-vous qu'il respecte les conventions de formatage de date Python.
