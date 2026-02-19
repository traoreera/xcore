# extension_loader.py

Le fichier `xcore/integration/plugins/extension_loader.py` charge, démarre et arrête les extensions déclarées dans `integration.yaml`.

## Rôle

- Import dynamique via `module.path:ClassName`
- Instanciation des services (`BaseService`)
- `setup()` + marquage ready
- Enregistrement dans `ServiceRegistry`
- Support des workers de fond (`async`, `thread`, `both`)
- Support des `background_jobs` APScheduler

## Classes clés

- `ServiceStatus`
- `ServiceWorkerState`
- `ServiceWorker`
- `ExtensionLoader`

## Méthodes clés

- `init_all()`
- `get(name)`, `get_optional(name)`, `has(name)`
- `status()`
- `shutdown_all()`

## Exemple YAML

```yaml
extensions:
  email:
    service: "myapp.email:EmailService"
    enabled: true
    background: true
    background_mode: async
    config:
      endpoint: "https://api.mail.local"
    env:
      API_KEY: "${EMAIL_API_KEY}"
```

## Contribution

- Ajouter des garde-fous explicites pour les erreurs d’import et de setup.
- Ne jamais laisser un worker en arrière-plan sans mécanisme d’arrêt.
