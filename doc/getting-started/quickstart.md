# Guide de Démarrage Rapide

Apprenez à utiliser XCore en moins de 5 minutes. Ce guide vous accompagne dans la création de votre premier plugin et l'exécution de votre première action.

## Étape 1 : Démarrer le serveur XCore

```bash
cd xcore
poetry run uvicorn app:app --reload --port 8082
```

Si tout est correct, vous verrez :
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8082
```

## Étape 2 : Créer votre premier plugin

Créez un plugin simple nommé "compteur" qui utilise le service de cache pour compter les appels.

```bash
mkdir -p plugins/compteur/src
```

Créez le manifeste `plugins/compteur/plugin.yaml` :

```yaml
name: compteur
version: 1.0.0
author: Votre Nom
description: Un plugin qui compte les appels via le service de cache
execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

resources:
  timeout_seconds: 10
```

Créez le code Python `plugins/compteur/src/main.py` :

```python
from xcore.sdk import (
    TrustedBase,
    AutoDispatchMixin,
    RoutedPlugin,
    action,
    route,
    ok,
    error
)

class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    """Plugin de comptage démontrant les bases de XCore."""

    async def on_load(self) -> None:
        """Appelé lors du chargement du plugin."""
        self.cache = self.get_service("cache")
        print("✅ Plugin Compteur chargé avec succès !")

    @action("increment")
    async def increment_ipc(self, payload: dict) -> dict:
        """Action IPC (appelable par d'autres plugins ou CLI)."""
        key = payload.get("key", "default_counter")

        # Récupère la valeur actuelle (0 si absent)
        val = await self.cache.get(f"count:{key}") or 0
        new_val = val + 1

        # Sauvegarde la nouvelle valeur
        await self.cache.set(f"count:{key}", new_val)

        return ok(counter=new_val, key=key)

    @route("/valeur/{key}", method="GET")
    async def get_valeur_http(self, key: str):
        """Route HTTP (exposée sur /plugin/compteur/valeur/{key})."""
        val = await self.cache.get(f"count:{key}") or 0
        return {"key": key, "valeur": val}
```

## Étape 3 : Tester le plugin

Le plugin est automatiquement détecté et chargé par XCore. Testez-le immédiatement via l'API IPC et l'API HTTP.

### Test via l'API IPC (JSON sur HTTP)

XCore expose une API système pour appeler les actions des plugins.

```bash
# Incrémenter le compteur 'test_1'
curl -X POST http://localhost:8082/plugin/ipc/compteur/increment \
  -H "Content-Type: application/json" \
  -H "X-Plugin-Key: change-me-in-production" \
  -d '{"payload": {"key": "test_1"}}'

# Réponse :
# {"status":"ok","plugin":"compteur","action":"increment","result":{"status":"ok","counter":1,"key":"test_1"}}
```

### Test via la route HTTP personnalisée

Les plugins Trusted peuvent exposer leurs propres endpoints REST.

```bash
# Consulter la valeur actuelle via la route HTTP du plugin
curl http://localhost:8082/plugin/compteur/valeur/test_1

# Réponse :
# {"key":"test_1","valeur":1}
```

## Étape 4 : Utiliser la CLI XCore

Vous pouvez également interagir avec vos plugins via l'outil en ligne de commande.

```bash
# Lister les plugins chargés
poetry run xcore plugin list

# Vérifier la santé du plugin
poetry run xcore plugin health
```

## Résumé des concepts clés

Dans ce guide, vous avez appris à :

✅ **Créer un manifeste** (`plugin.yaml`) pour déclarer votre plugin.
✅ **Utiliser les mixins** (`AutoDispatchMixin`, `RoutedPlugin`) pour simplifier le code.
✅ **Déclarer des actions IPC** avec le décorateur `@action`.
✅ **Déclarer des routes HTTP** avec le décorateur `@route`.
✅ **Accéder aux services partagés** (ici, le cache) via `self.get_service()`.

## Prochaines étapes

- [En savoir plus sur la création de plugins](../guides/creating-plugins.md)
- [Découvrir tous les services disponibles](../guides/services.md)
- [Comprendre le système d'événements](../guides/events.md)
- [Sécuriser vos plugins avec le Sandboxing](../guides/security.md)
