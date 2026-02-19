# utils.py (Hooks)

Le fichier `utils.py` dans le module `hooks` contient des fonctions utilitaires, des intercepteurs prédéfinis et des décorateurs avancés pour faciliter l'utilisation du système de hooks.

## Intercepteurs prédéfinis

Ces fonctions retournent des intercepteurs configurables que vous pouvez ajouter à votre `HookManager`.

### `logging_interceptor(log_level="info")`

Crée un intercepteur qui journalise chaque émission d'événement.

```python
xhooks.add_pre_interceptor("*", logging_interceptor("debug"))
```

### `rate_limit_interceptor(max_calls, window_seconds)`

Crée un intercepteur qui limite le taux d'émission d'un événement.

```python
xhooks.add_pre_interceptor("api.request", rate_limit_interceptor(100, 60.0))
```

### `debounce_interceptor(delay_seconds)`

Crée un intercepteur qui "déboucle" (debounce) les émissions répétitives d'un événement.

### `validation_interceptor(required_keys)`

Crée un intercepteur qui valide la présence de clés obligatoires dans `event.data`.

```python
xhooks.add_pre_interceptor("user.create", validation_interceptor(["username", "email"]))
```

## Processeurs de résultats prédéfinis

Ces fonctions traitent la liste des `HookResult` après l'exécution.

- `error_counting_processor(max_errors=10)`: Compte les erreurs consécutives d'un hook et logue un avertissement critique.
- `result_filter_processor(success_only=False)`: Filtre les résultats pour ne garder que les succès.
- `timing_processor(threshold_ms=1000.0)`: Logue un avertissement si un hook est trop lent.

## Décorateurs avancés

### `ConditionalHook(condition: Callable[[Event], bool])`

Permet d'exécuter un hook uniquement si une condition spécifique sur l'événement est remplie.

```python
@ConditionalHook(lambda e: e.data.get("admin") == True)
@xhooks.on("user.delete")
async def delete_user(event: Event):
    ...
```

### `retry_hook(max_retries=3, delay_seconds=1.0)`

Ajoute une logique de tentative automatique (retry) avec backoff exponentiel à un hook.

```python
@retry_hook(max_retries=3, delay_seconds=2.0)
@xhooks.on("api.call")
async def unreliable_task(event: Event):
    ...
```

### `memoized_hook(ttl_seconds=300.0)`

Met en cache le résultat d'un hook pendant une période donnée, basé sur le nom de l'événement et ses données.

## Chaînage de Hooks (`HookChain`)

Permet de créer facilement une suite de hooks dépendants les uns des autres.

```python
chain = HookChain(xhooks, "data.process")
chain.then(validate_data, priority=10)
chain.then(transform_data, priority=20)
chain.then(save_data, priority=30)
```

## Contribution

- Si vous ajoutez un nouvel utilitaire, assurez-vous qu'il suit le format `Callable` attendu par le `HookManager`.
- Testez les décorateurs pour vous assurer qu'ils n'introduisent pas de latence inutile dans la boucle d'événements.
- Documentez tout nouveau paramètre pour les processeurs de résultats.
