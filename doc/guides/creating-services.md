# Création de Services

Si les services intégrés (DB, Cache, Scheduler) ne suffisent pas, vous pouvez créer vos propres services pour partager des fonctionnalités complexes entre plugins.

## Qu'est-ce qu'un Service XCore ?

Un service est une instance singleton, gérée par le `ServiceContainer`, qui survit au cycle de vie individuel des plugins. Contrairement à un plugin qui fournit une logique métier, un service fournit une infrastructure technique.

## Étape 1 : Définir l'Interface du Service

Il est recommandé de créer une classe de base héritant de `BaseServiceProvider`.

```python
from xcore.services.base import BaseServiceProvider

class EmailService(BaseServiceProvider):
    def __init__(self, smtp_host, port):
        self.host = smtp_host
        self.port = port
        self._connected = False

    async def init(self):
        """Initialisation du service (appelé au démarrage du framework)."""
        print(f"Connexion au serveur SMTP {self.host}...")
        self._connected = True

    async def shutdown(self):
        """Fermeture propre du service."""
        print("Déconnexion SMTP.")
        self._connected = False

    async def send(self, to, subject, body):
        if not self._connected:
            raise RuntimeError("Service non connecté")
        print(f"Email envoyé à {to}")
```

## Étape 2 : Enregistrer le Service

L'enregistrement se fait via le `ServiceContainer` au démarrage de l'application ou dynamiquement via un plugin Trusted.

### Via un Plugin de Confiance (Recommandé pour les extensions)

```python
from xcore.sdk import TrustedBase

class EmailProviderPlugin(TrustedBase):
    async def on_load(self):
        # Création de l'instance du service
        service = EmailService(
            smtp_host=self.ctx.config.get("smtp_host"),
            port=self.ctx.config.get("smtp_port")
        )

        # Initialisation manuelle si nécessaire
        await service.init()

        # Enregistrement global
        # Il sera accessible via self.get_service("ext.email")
        self.ctx.services.register("ext.email", service)

    async def on_unload(self):
        # Nettoyage
        service = self.ctx.services.get("ext.email")
        await service.shutdown()
        self.ctx.services.unregister("ext.email")
```

## Étape 3 : Utiliser le Service dans d'autres Plugins

```python
class NotificationPlugin(TrustedBase):
    async def on_load(self):
        self.email = self.get_service("ext.email")

    async def notifier_utilisateur(self, email):
        await self.email.send(
            to=email,
            subject="Bienvenue",
            body="Merci d'avoir rejoint XCore !"
        )
```

## Étape 4 : Gestion de la Santé (Health Check)

Pour que votre service soit monitoré par la commande `xcore health`, implémentez la méthode `health()`.

```python
class EmailService(BaseServiceProvider):
    # ...
    def health(self) -> dict:
        return {
            "status": "ok" if self._connected else "error",
            "details": {
                "host": self.host,
                "connected": self._connected
            }
        }
```

## Cycle de vie des Services

L'ordre d'initialisation est crucial :
1. **Services Core** (DB, Cache) sont initialisés en premier.
2. **Services Extensions** (les vôtres) sont initialisés ensuite.
3. **Plugins** sont chargés en dernier, garantissant que tous les services sont prêts.

## Bonnes Pratiques

1. **Namespacing** : Préfixez toujours vos services personnalisés par `ext.` (ex: `ext.billing`, `ext.search`) pour éviter les conflits avec les futurs services officiels de XCore.
2. **Lazy Loading** : Si votre service consomme beaucoup de ressources, différez la connexion réelle jusqu'au premier appel ou utilisez `asyncio.create_task` dans `init()`.
3. **Thread Safety** : Si votre service est appelé par des plugins Trusted en multi-threading, assurez-vous qu'il est thread-safe (utilisez des verrous si nécessaire).
4. **Documentation** : Documentez l'interface de votre service afin que les développeurs de plugins sachent quelles méthodes appeler.
