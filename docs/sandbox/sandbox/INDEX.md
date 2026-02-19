# Module Sandbox Runtime

Contient le runtime sandbox bas niveau (process, IPC, scan, quotas, snapshot).

## Fichiers

```{toctree}
:maxdepth: 1

disk_watcher
ipc
rate_limiter
scanner
snapshot
supervisor
worker
```

## Contribution

- Priorité à la robustesse (timeouts, erreurs, récupération crash).
- Toute ouverture de capacité doit être analysée sécurité d’abord.
