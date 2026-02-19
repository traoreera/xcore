# supervisor.py

Le fichier `xcore/sandbox/sandbox/supervisor.py` supervise le process sandboxed d’un plugin.

## Responsabilités

- Spawn subprocess worker
- Ping health-check
- Restart automatique avec limites
- Vérification quota disque
- Collecte status (PID, uptime, restarts)

## Types

- `ProcessState`
- `SupervisorConfig`
- `SandboxSupervisor`

## API clé

- `start()`
- `call(action, payload)`
- `stop()`
- `status()`

## Détails sécurité

- Environnement subprocess minimal (pas d’héritage complet de secrets)
- Limite mémoire via variable `_SANDBOX_MAX_MEM_MB` appliquée côté worker

## Contribution

- Toute modification restart/health doit être testée sur crash réel.
- Conserver un shutdown non bloquant même en état dégradé.
