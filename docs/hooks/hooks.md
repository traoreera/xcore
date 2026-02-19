# hooks.py

Le fichier `hooks.py` contient le coeur du système d'événements de xcore. Il fournit une architecture d'événements complète avec support des priorités, wildcards et intercepteurs.

## Classes principales

### `Event`

L'objet passé à chaque hook lors de son exécution.

```python
class Event:
    name: str # Nom de l'événement émis
    data: Dict[str, Any] # Données de l'événement
    metadata: Dict[str, Any] # Métadonnées additionnelles
    cancelled: bool # Si True, les hooks suivants ne seront pas exécutés
    stop_propagation: bool # Si True, arrête la propagation à l'instant T
```

- `cancel()`: Annule l'événement (empêche toute exécution).
- `stop()`: Arrête la propagation vers les hooks restants (ceux qui ont déjà tourné restent valides).

### `HookManager`

Le registre central de tous les hooks. C'est l'objet principal que vous manipulerez.

#### Méthodes d'abonnement

- `on(event_name, priority=50, once=False, timeout=None)`: Décorateur pour enregistrer un hook.
- `once(event_name, priority=50, timeout=None)`: Décorateur pour un hook à exécution unique.
- `unregister(event_name, func)`: Supprime un hook spécifique.
- `clear(event_name=None)`: Vide tout ou partie du registre.

#### Méthodes d'émission

- `async emit(event_name, data=None, **kwargs)`: Émet un événement et exécute tous les hooks correspondants. Retourne une liste de `HookResult`.
- `async emit_until_first(event_name, data=None, **kwargs)`: Retourne le premier résultat non-None.
- `async emit_until_success(event_name, data=None, **kwargs)`: Retourne le premier `HookResult` réussi.

#### Intercepteurs et Processeurs

- `add_pre_interceptor(event_name, func, priority=50)`: Ajoute un middleware s'exécutant AVANT les hooks.
- `add_post_interceptor(event_name, func, priority=50)`: Ajoute un middleware s'exécutant APRÈS les hooks.
- `add_result_processor(event_name, processor)`: Ajoute une fonction de transformation des résultats finaux.

### `HookResult`

Contient le résultat de l'exécution d'un seul hook.

```python
class HookResult:
    hook_name: str # Nom de la fonction du hook
    event_name: str # Nom de l'événement original
    result: Any # Donnée retournée par la fonction
    error: Optional[Exception] # Exception si échec
    execution_time_ms: float # Temps d'exécution en ms
    cancelled: bool # Si l'événement a été annulé
```

## Wildcards (Motifs)

Le système supporte `fnmatch` pour les noms d'événements :
- `plugin.*`: Match `plugin.loaded`, `plugin.failed`, etc.
- `*.update`: Match `user.update`, `settings.update`, etc.

## Exemple : Intercepteur

```python
from xcore.hooks import Event, InterceptorResult

async def security_check(event: Event):
    if not event.data.get("token"):
        return InterceptorResult.CANCEL # Annule tout !
    return InterceptorResult.CONTINUE

xhooks.add_pre_interceptor("api.*", security_check)
```

## Détails Techniques

- L'ordonnancement est géré par une liste triée par priorité (`priority`) à chaque enregistrement.
- L'exécution asynchrone est gérée via `asyncio`.
- Les métriques de performance sont stockées dans `_metrics` et accessibles via `get_metrics()`.

## Contribution

- Assurez-vous que les exceptions levées dans les hooks sont capturées (le `HookManager` le fait, mais l'utilisateur doit être informé).
- Maintenez la compatibilité avec les wildcards lors de toute modification de `_get_matching_hooks`.
