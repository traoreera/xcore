# Système d'Événements et Hooks XCore

XCore utilise une architecture pilotée par les événements (Event-Driven) pour permettre une communication découplée entre les plugins.

## 1. Concept de base

Le système repose sur deux types d'interactions majeures :
- **Event Bus** : Diffusion asynchrone d'informations (Pub/Sub).
- **Hooks** : Interception asynchrone permettant de modifier des données ou d'interrompre un flux.

---

## 2. Event Bus : Publication et Souscription

Le bus d'événements permet d'émettre des messages à travers tout le système.

### S'abonner à un événement

Les abonnements se font généralement dans la méthode `on_load`.

```python
from xcore.sdk import TrustedBase

class NotificationPlugin(TrustedBase):
    async def on_load(self):
        # Abonnement standard
        self.ctx.events.on("user.registered", self.send_email)

        # Abonnement avec wildcards
        self.ctx.events.on("order.*", self.log_order_event)

    async def send_email(self, event):
        user_id = event.data["user_id"]
        print(f"Envoi d'un email de bienvenue à {user_id}")

    async def log_order_event(self, event):
        print(f"Action {event.name} sur la commande {event.data['id']}")
```

### Émettre un événement

```python
class RegistrationPlugin(TrustedBase):
    async def register_user(self, user_id):
        # ... logique métier ...

        # Émission asynchrone
        await self.ctx.events.emit("user.registered", {
            "user_id": user_id,
            "ts": 123456789
        })
```

---

## 3. Gestion Avancée : Priorités et Flux

### Contrôle de l'ordre d'exécution (Priorité)

Vous pouvez définir une priorité (défaut: 50) pour chaque handler. Les handlers avec une priorité plus élevée (ex: 100) s'exécutent en premier.

```python
# S'exécute AVANT les autres (priorité 100 > 50)
self.ctx.events.on("order.payment", self.check_fraud, priority=100)

# S'exécute APRÈS (priorité 10 < 50)
self.ctx.events.on("order.payment", self.send_invoice, priority=10)
```

### Arrêt de propagation (`stop`)

Un handler peut décider d'interrompre l'exécution des handlers suivants pour un événement donné.

```python
async def check_fraud(self, event):
    if is_fraudulent(event.data):
        print("ALERTE : Fraude détectée. Arrêt de la propagation.")
        event.stop()  # Les handlers avec une priorité < 100 ne seront PAS appelés
```

---

## 4. Hooks : Interception et Modification

Les hooks sont des événements particuliers conçus pour être interceptés afin de modifier leur contenu avant que l'action finale ne soit effectuée.

### Utiliser un Hook pour modifier des données

```python
class ContentPlugin(TrustedBase):
    async def on_load(self):
        # Hook pour modifier le texte avant sauvegarde
        self.ctx.hooks.on("content.saving", self.censor_text)

    async def censor_text(self, event):
        text = event.data.get("text", "")
        # Modification directe de l'objet 'data' de l'événement
        event.data["text"] = text.replace("gros-mot", "****")
```

### Annulation d'une action (`cancel`)

Un hook peut également être "annulé", signalant à l'émetteur que l'opération ne doit pas se poursuivre.

```python
async def validate_order(self, event):
    if event.data["total"] > 10000:
        # Annule l'événement et arrête la propagation
        event.cancel()
        print("Commande trop élevée, annulation via Hook.")
```

---

## 5. Événements Système Natifs

XCore émet plusieurs événements natifs auxquels vos plugins peuvent réagir :

| Événement | Description |
|-----------|-------------|
| `xcore.boot` | Le framework démarre. |
| `xcore.plugins.booted` | Tous les plugins ont été chargés. |
| `plugin.<nom>.loaded` | Un plugin spécifique a été chargé. |
| `plugin.<nom>.reloaded`| Un plugin a été rechargé à chaud. |
| `service.<nom>.ready` | Un service (DB, Cache) est prêt. |
| `security.violation` | Une violation de sandbox a été détectée. |

---

## 6. Performances et Optimisations

XCore optimise le bus d'événements pour les charges de production :

- **Cache de réflexion** : Le type de chaque handler (`async` ou `sync`) est mis en cache lors de l'enregistrement pour éviter d'utiliser `inspect` à chaque émission (gain de performance de ~30x).
- **Parallélisme contrôlé** : Par défaut, `emit` utilise `asyncio.gather` pour exécuter les handlers en parallèle, sauf si l'ordre séquentiel est requis (ex: pour respecter `event.stop()`).
- **Isolation des exceptions** : Une erreur dans un handler ne fait pas échouer l'émission globale vers les autres handlers.
