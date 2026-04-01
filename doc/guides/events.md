# Système d'Événements et de Hooks

XCore utilise un `EventBus` asynchrone pour permettre une communication découplée entre les plugins et le noyau.

## Fonctionnement de l'EventBus

L' `EventBus` permet de publier des événements (`emit`) et d'y souscrire (`on`). Il supporte nativement :
- La gestion des **priorités** (les handlers avec une priorité plus élevée sont exécutés en premier).
- La propagation contrôlée (possibilité d'arrêter la chaîne de handlers via `event.stop()`).
- Le filtrage par **wildcards** (ex: `user.*`).

### Souscription aux événements

```python
class MyPlugin(TrustedBase):
    async def on_load(self) -> None:
        # Souscription simple
        self.ctx.events.on("user.login", self.handle_login)

        # Souscription avec priorité élevée (défaut: 0)
        self.ctx.events.on("order.created", self.validate_order, priority=100)

        # Souscription avec wildcard
        self.ctx.events.on("database.*", self.log_db_ops)
```

### Émission d'événements

```python
async def create_user(self, data):
    # Logique de création...
    user_id = 123

    # Émission asynchrone
    await self.ctx.events.emit("user.created", {"id": user_id, "name": data["name"]})

    # Émission synchrone (fire-and-forget)
    self.ctx.events.emit_sync("audit.log", {"action": "user_creation"})
```

## Gestion des Wildcards

XCore utilise `fnmatch` pour la résolution des patterns d'événements.

- `user.*` : Correspond à `user.login`, `user.logout`, `user.created`.
- `*.error` : Correspond à `db.error`, `plugin.error`, `auth.error`.
- `*` : Correspond à TOUS les événements du système (utile pour le logging global).

## Cycle de vie d'un événement

Lorsqu'un événement est émis :
1. L' `EventBus` collecte tous les handlers dont le pattern correspond au nom de l'événement.
2. Les handlers sont triés par **priorité décroissante**.
3. Chaque handler est exécuté séquentiellement.
4. Si un handler appelle `event.stop()`, l'exécution de la chaîne s'arrête immédiatement pour cet événement.
5. Si un handler appelle `event.cancel()` (spécifique aux Hooks), l'action parente peut être annulée.

## Le Système de Hooks

Les Hooks sont des événements spéciaux utilisés pour intercepter et modifier le comportement du framework ou d'un plugin.

```python
async def on_load(self) -> None:
    # Hook avant le traitement d'un paiement
    self.ctx.hooks.on("payment.process", self.check_fraud)

async def check_fraud(self, event):
    if event.data["amount"] > 10000:
        # Annule l'action liée au hook
        event.cancel()
        event.data["reason"] = "Potential fraud detected"
```

## Événements Système Notables

| Événement | Description | Payload |
|-----------|-------------|---------|
| `xcore.booted` | Le framework a fini de démarrer | `{}` |
| `plugin.loaded` | Un plugin a été chargé avec succès | `{"name": "...", "mode": "..."}` |
| `permission.deny` | Une permission a été refusée | `{"plugin": "...", "resource": "...", "action": "..."}` |
| `service.error` | Une erreur est survenue dans un service | `{"service": "...", "error": "..."}` |

## Bonnes Pratiques

1. **Nettoyage** : Pensez à vous désabonner dans `on_unload` pour éviter les fuites de mémoire.
   ```python
   async def on_unload(self):
       self.ctx.events.unsubscribe("user.login", self.handle_login)
   ```
2. **Handlers non-bloquants** : Comme l'EventBus est asynchrone, évitez les opérations CPU-intensive ou I/O bloquantes à l'intérieur d'un handler. Déléguez au `scheduler` si nécessaire.
3. **Priorités** : Utilisez des constantes pour vos priorités afin de maintenir la cohérence (ex: `PRIORITY_CRITICAL = 1000`, `PRIORITY_MONITORING = -100`).
