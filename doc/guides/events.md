# Système d'Événements et Hooks

XCore utilise une architecture pilotée par les événements (Event-Driven) pour permettre une communication découplée et extensible entre les plugins et le noyau.

## Concept de base

Le système repose sur deux composants majeurs :
1. **Event Bus** : Pour la diffusion d'informations (Publish/Subscribe).
2. **Hooks** : Pour permettre aux plugins d'intercepter ou de modifier le comportement d'autres composants.

## Event Bus

Le bus d'événements permet d'émettre des messages à travers tout le système.

### Émettre un événement

```python
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    async def trigger_something(self):
        # Émission asynchrone
        await self.ctx.events.emit("user.registered", {
            "user_id": 123,
            "email": "alice@example.com"
        })
```

### S'abonner à un événement

Les abonnements se font généralement dans la méthode `on_load`.

```python
class NotificationPlugin(TrustedBase):
    async def on_load(self):
        # Inscription au bus
        self.ctx.events.on("user.registered", self.send_welcome_email)

    async def send_welcome_email(self, event):
        user_data = event.data
        print(f"Envoi d'un email à {user_data['email']}")
```

### Priorités et Arrêt de propagation

Vous pouvez contrôler l'ordre d'exécution des handlers.

```python
# Un handler prioritaire (exécuté en premier)
self.ctx.events.on("order.created", self.check_fraud, priority=100)

# Un handler normal (défaut: 50)
self.ctx.events.on("order.created", self.log_order, priority=50)

async def check_fraud(self, event):
    if is_fraudulent(event.data):
        # Arrête l'exécution des handlers suivants pour cet événement
        event.stop()
        print("Commande frauduleuse bloquée !")
```

## Système de Hooks

Les hooks sont des points d'extension spécifiques qui permettent de modifier des données ou de valider des actions avant qu'elles ne soient finalisées.

### Utiliser un Hook

```python
class FilterPlugin(TrustedBase):
    async def on_load(self):
        # Intercepte le hook 'content.processing'
        self.ctx.hooks.on("content.processing", self.filter_bad_words)

    async def filter_bad_words(self, event):
        # Modifie directement les données de l'événement
        text = event.data.get("text", "")
        event.data["text"] = text.replace("mauvais", "****")
```

### Annulation d'Action

Contrairement aux événements simples, un hook peut être annulé, ce qui signale à l'émetteur que l'action ne doit pas être poursuivie.

```python
async def validate_payment(self, event):
    if event.data["amount"] > 5000:
        event.cancel(reason="Montant trop élevé sans validation manuelle")
```

## Événements Système

XCore émet plusieurs événements natifs auxquels vos plugins peuvent réagir :

| Événement | Description |
|-----------|-------------|
| `xcore.boot` | Le framework démarre. |
| `xcore.plugins.booted` | Tous les plugins ont été chargés. |
| `plugin.<name>.loaded` | Un plugin spécifique a été chargé. |
| `plugin.<name>.reloaded`| Un plugin a été rechargé à chaud. |
| `service.<name>.ready` | Un service (DB, Cache) est prêt. |
| `security.violation` | Une violation de sandbox a été détectée. |

## Performances et Bonnes Pratiques

- **Asynchronisme** : Le bus d'événements gère nativement les handlers `async` et synchrones.
- **Cache de réflexion** : XCore met en cache le type de chaque handler pour éviter l'utilisation coûteuse de `inspect` lors de chaque émission (gain de performance de ~30x).
- **Éviter les boucles** : Soyez vigilant à ne pas émettre un événement qui déclenche un handler qui émet à nouveau le même événement.
- **Nettoyage** : Bien que XCore gère le nettoyage automatique au déchargement, il est de bonne pratique d'utiliser `self.ctx.events.unsubscribe` dans `on_unload` si vous créez des abonnements dynamiques.
