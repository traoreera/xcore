# Création de Plugins

Ce guide vous accompagne dans la création de plugins XCore, du plus simple au plus avancé.

## Structure d'un Plugin

Un plugin XCore est un répertoire contenant au minimum deux fichiers :

```text
mon_plugin/
├── plugin.yaml      # Le manifeste (métadonnées)
└── src/
    └── main.py      # Le point d'entrée (code Python)
```

## Étape 1 : Le Manifeste (`plugin.yaml`)

Le manifeste définit comment XCore doit charger et isoler votre code.

```yaml
name: mon_hello_world
version: "1.0.0"
author: "Moi"
description: "Mon premier plugin"
execution_mode: "trusted" # Utilisez "sandboxed" pour plus de sécurité
entry_point: "src/main.py"

# Facultatif : dépendances sur d'autres plugins
requires:
  - plugin_authentification >= 2.0.0

# Facultatif : permissions requises
permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
```

## Étape 2 : Le Code (`src/main.py`)

Votre plugin doit définir une classe nommée `Plugin` héritant de `TrustedBase`.

### Exemple Minimaliste

```python
from xcore.sdk import TrustedBase, ok, error

class Plugin(TrustedBase):
    async def handle(self, action: str, payload: dict) -> dict:
        if action == "dire_bonjour":
            nom = payload.get("nom", "Inconnu")
            return ok(message=f"Bonjour {nom} !")

        return error(f"Action {action} inconnue")
```

## Étape 3 : Utilisation du SDK Avancé

Pour des plugins plus complexes, utilisez les mixins et décorateurs pour simplifier votre code.

### Dispatch Automatique et Routes HTTP

```python
from xcore.sdk import (
    TrustedBase,
    AutoDispatchMixin,
    RoutedPlugin,
    action,
    route,
    ok
)

class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):

    # --- Action IPC (Appelable par d'autres plugins ou CLI) ---
    @action("calculer")
    async def faire_calcul(self, payload: dict):
        resultat = payload.get("a", 0) + payload.get("b", 0)
        return ok(total=resultat)

    # --- Route HTTP (Exposée sur /plugins/mon_hello_world/statut) ---
    @route("/statut", method="GET")
    async def voir_statut(self):
        return {"etat": "actif", "version": self.ctx.version}
```

## Étape 4 : Accès aux Services

Les services sont le moyen privilégié pour interagir avec le reste du système.

```python
class Plugin(TrustedBase):
    async def on_load(self):
        # Initialisation du service DB
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

    async def sauvegarder_donnee(self, cle, valeur):
        # Utilisation du cache
        await self.cache.set(cle, valeur, ttl=600)

        # Utilisation de la DB
        with self.db.session() as session:
            session.execute("INSERT INTO logs (cle) VALUES (:c)", {"c": cle})
```

## Étape 5 : Communication par Événements

Les plugins peuvent communiquer de manière asynchrone via le bus d'événements.

```python
class Plugin(TrustedBase):
    async def on_load(self):
        # S'abonner à un événement produit par un autre plugin
        self.ctx.events.on("paiement.valide", self.preparer_commande)

    async def preparer_commande(self, event):
        commande_id = event.data["id"]
        print(f"Préparation de la commande {commande_id}")

        # Émettre un nouvel événement
        await self.ctx.events.emit("commande.prete", {"id": commande_id})
```

## Modes d'Exécution : Trusted vs Sandboxed

| Caractéristique | Trusted | Sandboxed |
|-----------------|---------|-----------|
| **Vitesse** | Maximale (In-process) | Légère latence (IPC) |
| **Sécurité** | Faible (Accès total) | Élevée (Isolé) |
| **Accès Fichiers** | Illimité | Restreint au dossier `data/` |
| **Modules Python** | Tous | Whitelist restreinte |
| **Utilisation** | Plugins internes | Plugins tiers / Marketplace |

### Passer en mode Sandboxed
Il suffit de changer `execution_mode: "sandboxed"` dans votre `plugin.yaml`. XCore s'occupe du reste : création du sous-processus, mise en place des guards et du pipeline IPC.

## Test et Validation

Avant de déployer, validez votre manifeste avec la CLI :
```bash
xcore plugin validate ./plugins/mon_plugin
```

Et testez le comportement en sandbox :
```bash
xcore sandbox run mon_plugin
```
