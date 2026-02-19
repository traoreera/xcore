# appcfg.py

Le fichier `appcfg.py` contient les instances globales de configuration et de gestion des hooks partagées par toute l'application xcore.

## Rôle

Ce fichier sert de point d'accès centralisé pour :
1. L'instance globale de configuration `xcfg`.
2. L'instance globale du gestionnaire de hooks `xhooks`.

## Structure

```python
from xcore.configurations import core
from xcore.hooks import HookManager

# Instance globale de configuration xcore
# Elle est initialisée avec les valeurs par défaut ou provenant de variables d'environnement
xcfg = core.Xcorecfg(conf=core.Configure())

# Instance globale du gestionnaire de hooks (HookManager)
# Utilisée pour la communication inter-composants
xhooks = HookManager()
```

## Utilisation

Importez ces instances partout où vous avez besoin d'accéder à la configuration ou d'émettre/écouter des hooks.

### Exemple : Accès à la configuration

```python
from xcore.appcfg import xcfg

print(xcfg.app.name) # Affiche le nom de l'application
```

### Exemple : Émission d'un hook

```python
from xcore.appcfg import xhooks

await xhooks.emit("app_ready", payload={"status": "running"})
```

## Détails Techniques

- `xcfg`: Est un objet `Xcorecfg` qui encapsule les paramètres définis dans `xcore.configurations.core`.
- `xhooks`: Est un `HookManager` singleton (si importé depuis `appcfg.py`) qui gère l'enregistrement et l'appel des fonctions de rappel (callbacks).

## Contribution

Toute modification dans `appcfg.py` doit rester minimale pour éviter les imports circulaires. Si une nouvelle classe de configuration est ajoutée, elle doit être importée depuis `xcore.configurations`.
