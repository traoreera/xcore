# scheduler.py (SchedulerService)

Le fichier `xcore/integration/services/scheduler.py` encapsule APScheduler pour les jobs planifiés.

## Rôle

- Charger les jobs depuis `integration.yaml`
- Support des triggers `interval` et `cron`
- Backend jobstore mémoire/Redis/SQLAlchemy selon config

## API publique

- `init()`
- `add_job(func, trigger="interval", job_id=None, **kwargs)`
- `remove_job(job_id)`
- `pause_job(job_id)`
- `resume_job(job_id)`
- `list_jobs()`
- `shutdown(wait=True)`
- `is_running`

## Exemple YAML

```yaml
scheduler:
  enabled: true
  jobs:
    - id: cleanup
      func: myapp.tasks:cleanup
      trigger: interval
      minutes: 10
```

## Contribution

- Garder les imports APScheduler protégés (`ImportError`).
- Tester les jobs dynamiques ajoutés à chaud.
