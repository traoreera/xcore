# Créer des Services

Les services sont des composants globaux partagés entre tous les plugins. Contrairement aux plugins, ils n'ont pas de routes HTTP propres mais fournissent des APIs programmatiques (DB, Cache, etc.).

## 1. Définir un Service personnalisé

Pour créer un service, vous devez hériter de `BaseServiceProvider` (ou `BaseService` selon le contexte du conteneur).

```python
from xcore.services.base import BaseServiceProvider

class MyCustomService(BaseServiceProvider):
    def init(self):
        """Initialisation du service lors du boot du framework."""
        self.config = self.container.config.get("my_service", {})
        self.client = self._connect_to_resource()

        # Enregistrement dans le conteneur
        self.container.register("custom_tool", self.client)

    def shutdown(self):
        """Nettoyage lors de l'arrêt du serveur."""
        self.client.close()

    def _connect_to_resource(self):
        # Logique de connexion...
        return "ConnectedClient"
```

## 2. Enregistrer le Service

Les services personnalisés (Extensions) se configurent dans le fichier `xcore.yaml` :

```yaml
services:
  extensions:
    my_service:
      module: "mon_package.services.MyCustomService"
      config:
        api_key: "${MY_API_KEY}"
        timeout: 30
```

## 3. Cycle de Vie et Santé

Chaque service peut implémenter une méthode `health_check` qui sera utilisée par le système de monitoring global.

```python
def health_check(self) -> tuple[bool, str]:
    if self.client.is_alive():
        return True, "Service opérationnel"
    return False, "Connexion perdue"
```

## 4. Scoping (Visibilité)

Par défaut, un service enregistré est **Public**. Si vous développez un plugin qui expose un service interne, vous pouvez restreindre sa visibilité dans le `plugin.yaml` du plugin exportateur :

```yaml
# plugin.yaml
resources:
  services:
    internal_tool:
      scope: private
```

## 5. Utilisation dans un Plugin

Une fois enregistré, le service est accessible via le SDK :

```python
class MyPlugin(TrustedBase):
    async def on_load(self):
        # Accès au service par son nom d'enregistrement
        self.tool = self.get_service("custom_tool")
```

## Bonnes Pratiques pour les Services

1. **Lazy Loading** : Si l'initialisation est lourde, différez-la jusqu'à la première utilisation si possible.
2. **Thread-Safety** : Les services étant partagés, assurez-vous qu'ils supportent les accès concurrents.
3. **Logs** : Utilisez le logger du conteneur (`self.container.logger`) pour garder une trace de l'initialisation.
4. **Timeouts** : Définissez toujours des timeouts sur les connexions réseau pour éviter de bloquer tout le framework.
