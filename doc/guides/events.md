# Événements & Hooks

XCore utilise un `EventBus` asynchrone pour la communication découplée entre le kernel et les plugins.

---

## EventBus

### S'abonner à un événement

```python
from xcore.kernel.events.bus import EventBus

# Depuis un plugin — accès via self.ctx.events
async def on_load(self):
    bus: EventBus = self.ctx.events

    @bus.on("user.created")
    async def welcome_user(event):
        email = event.data.get("email")
        await self._send_welcome(email)

    # Handler one-shot (se désabonne après le premier appel)
    @bus.once("system.ready")
    async def on_ready(event):
        await self._init_data()
```

### Émettre un événement

```python
# Parallel (gather=True par défaut) — tous les handlers en parallèle
await self.ctx.events.emit("order.created", {
    "order_id": 42,
    "user_id": 7,
    "amount": 99.90,
})

# Séquentiel avec propagation contrôlable
await self.ctx.events.emit("payment.processing", data, gather=False)

# Fire-and-forget depuis du code synchrone
self.ctx.events.emit_sync("metrics.tick", {"ts": time.time()})
```

### Wildcards

```python
# S'abonner à tous les événements "order.*"
@bus.on("order.*")
async def handle_all_orders(event):
    logger.info(f"Ordre: {event.name} — {event.data}")

# S'abonner à tous les événements
@bus.on("*")
async def log_all(event):
    logger.debug(f"Event: {event.name}")
```

### Priorités

Les handlers sont appelés par ordre de priorité décroissante (défaut : 50).

```python
@bus.on("request.incoming", priority=100)
async def auth_check(event):
    # Exécuté en premier
    ...

@bus.on("request.incoming", priority=10)
async def log_request(event):
    # Exécuté en dernier
    ...
```

### Introspection

```python
# Lister tous les événements abonnés
events = bus.list_events()
# {"user.created": ["welcome_user", "audit_log"], "order.*": ["handle_all_orders"]}

# Nombre de handlers pour un événement
count = bus.handler_count("user.created")

# Désabonner un handler
bus.unsubscribe("user.created", welcome_user)

# Vider le bus
bus.clear()                    # tout
bus.clear("user.created")      # un événement spécifique
```

---

## Événements système

XCore émet des événements internes auxquels les plugins peuvent s'abonner :

| Événement | Données | Déclenchement |
|:----------|:--------|:--------------|
| `plugin.loaded` | `{"name": str, "version": str}` | Après chargement réussi |
| `plugin.unloaded` | `{"name": str}` | Après déchargement |
| `plugin.failed` | `{"name": str, "error": str}` | Après échec de chargement |
| `plugin.reloaded` | `{"name": str}` | Après rechargement à chaud |
| `service.ready` | `{"name": str}` | Après init d'un service |
| `system.shutdown` | `{}` | Avant arrêt du kernel |

---

## HookManager

Les hooks permettent d'intercepter des points précis du cycle de vie sans passer par le bus.

```python
# Accès via self.ctx.hooks
hooks = self.ctx.hooks

# Enregistrer un hook avant une action
@hooks.before("plugin.call")
async def before_call(context):
    context["start_time"] = time.monotonic()

# Enregistrer un hook après une action
@hooks.after("plugin.call")
async def after_call(context):
    duration = time.monotonic() - context.get("start_time", 0)
    logger.info(f"Appel terminé en {duration:.3f}s")
```

---

## Patterns communs

### Communication entre plugins via événements

```python
# Plugin A — émet
@action("create_order")
async def create_order(self, payload: dict) -> dict:
    order = await self._save_order(payload)
    await self.ctx.events.emit("order.created", {
        "order_id": order.id,
        "user_id": payload["user_id"],
        "total": order.total,
    })
    return ok(order_id=order.id)

# Plugin B — réagit
async def on_load(self):
    @self.ctx.events.on("order.created")
    async def send_confirmation(event):
        await self._send_email(event.data["user_id"], event.data["order_id"])
```

### Invalidation de cache sur événement

```python
async def on_load(self):
    self.cache = self.get_service("cache")

    @self.ctx.events.on("user.updated")
    async def invalidate_user_cache(event):
        user_id = event.data.get("user_id")
        await self.cache.delete(f"user:{user_id}")
        await self.cache.delete(f"profile:{user_id}")
```
