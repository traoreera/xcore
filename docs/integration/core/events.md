# events.py (Event Bus)

Le fichier `events.py` dans le module `integration/core` fournit le bus d'événements asynchrone pour la communication inter-services dans xcore.

## Rôle

Le `EventBus` est un système de type `EventEmitter` qui permet aux différents composants de l'application de s'abonner et d'émettre des événements asynchrones. Son rôle est de :
- Permettre un couplage lâche entre les services (un service peut émettre un événement sans savoir qui l'écoute).
- Supporter les priorités d'exécution pour les gestionnaires (handlers).
- Permettre l'arrêt de la propagation d'un événement.
- Gérer les abonnements uniques (`once`).

## Classes principales

### `Event`

L'objet émis à chaque déclenchement d'un événement.

```python
class Event:
    name: str # Nom de l'événement émis
    data: Dict[str, Any] # Données de l'événement
    source: Optional[str] # Source de l'événement
    propagate: bool # Si False, stoppe la propagation vers les suivants
```

- `stop_propagation()`: Arrête l'événement (empêche toute exécution ultérieure).

### `EventBus`

Le gestionnaire central des événements.

#### Méthodes d'abonnement

- `on(event_name, priority=50, name=None)`: Décorateur pour s'abonner à un événement.
- `once(event_name, priority=50)`: Décorateur pour s'abonner une seule fois.
- `subscribe(event_name, handler, priority=50, once=False, name=None)`: Méthode d'enregistrement bas niveau.
- `unsubscribe(event_name, handler)`: Supprime un abonnement spécifique.

#### Méthodes d'émission

- `async emit(event_name, data=None, source=None, gather=True)`: Émet un événement. Si `gather=True`, les handlers s'exécutent en parallèle.
- `emit_sync(event_name, data=None)`: Wrapper synchrone (fire-and-forget) pour `emit()`.

## Exemple d'utilisation

```python
from xcore.integration.core.events import get_event_bus, Event

bus = get_event_bus()

# S'abonner
@bus.on("database.connected")
async def on_db_connected(event: Event):
    print(f"Base de données connectée : {event.data.get('url')}")

# Émettre
await bus.emit("database.connected", data={"url": "sqlite:///app.db"})
```

## Détails Techniques

- L'ordonnancement est géré par une liste triée par priorité (`priority`). Plus la priorité est élevée (ex: 100), plus le handler s'exécute tôt.
- `asyncio.gather` est utilisé pour l'exécution parallèle des handlers par défaut.
- `EventBus` supporte aussi bien les handlers `def` que `async def`.

## Contribution

- Le `EventBus` est un composant critique ; toute modification de performance doit être validée.
- Conservez le singleton global accessible via `get_event_bus()`.
- Lors de l'émission avec `gather=False`, assurez-vous de respecter scrupuleusement le drapeau `propagate`.
