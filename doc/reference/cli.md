# CLI Reference

Le CLI `xcore` expose des commandes pour gérer les plugins, le sandbox, le marketplace, les services et les processus worker.

```bash
xcore --help
xcore --version
```

---

## `xcore plugin`

### `list`

```bash
xcore plugin list
```

### `info <name>`

```bash
xcore plugin info mon_plugin
```

### `load <name>`

```bash
xcore plugin load mon_plugin [--host 127.0.0.1] [--port 8000] [--key <api_key>]
```

### `reload <name>`

```bash
xcore plugin reload mon_plugin
```

### `install <name>`

```bash
xcore plugin install auth_plugin                          # marketplace (défaut)
xcore plugin install mon_plugin --source zip --url <url>  # archive zip
xcore plugin install mon_plugin --source git --url <url>  # dépôt git
```

### `remove <name>`

```bash
xcore plugin remove mon_plugin
```

### `sign <path>`

```bash
xcore plugin sign plugins/mon_plugin --key "ma_cle_secrete"
```

### `verify <path>`

```bash
xcore plugin verify plugins/mon_plugin --key "ma_cle_secrete"
```

### `validate <path>`

```bash
xcore plugin validate plugins/mon_plugin
```

### `health`

```bash
xcore plugin health
```

---

## `xcore sandbox`

### `run <name>`

```bash
xcore sandbox run mon_plugin
```

### `limits <name>`

```bash
xcore sandbox limits mon_plugin
```

### `network <name>`

```bash
xcore sandbox network mon_plugin
```

### `fs <name>`

```bash
xcore sandbox fs mon_plugin
```

---

## `xcore marketplace`

```bash
xcore marketplace list
xcore marketplace trending
xcore marketplace search "authentication"
xcore marketplace show auth_plugin
xcore marketplace rate auth_plugin --score 5
```

---

## `xcore services status`

```bash
xcore services status
xcore services status --json
```

---

## `xcore health`

```bash
xcore health
xcore health --json
```

---

## `xcore worker`

Gère les processus FastAPI (uvicorn) et Celery en arrière-plan avec fichiers PID et logs séparés.

### `start [api|celery|all]`

Lance un ou plusieurs processus. Cible par défaut : `all`.

```bash
xcore worker start                      # API + Celery (foreground)
xcore worker start --detach             # arrière-plan, PIDs dans .xcore/pids/
xcore worker start api --reload         # API seule en dev
xcore worker start celery -Q default,emails -c 4
xcore worker start --host 0.0.0.0 --port 8080
```

| Option | Description |
|:-------|:------------|
| `--detach / -d` | Lance en arrière-plan |
| `--loglevel / -l` | Niveau de log (`debug`…`critical`) |
| `--app` | App ASGI (`main:app`) |
| `--host` | Adresse d'écoute (défaut: `integration.yaml → server.host`) |
| `--port / -p` | Port (défaut: `integration.yaml → server.port`) |
| `--workers / -w` | Workers uvicorn |
| `--reload` | Auto-reload uvicorn |
| `--queues / -Q` | Files Celery (défaut: `integration.yaml → xworker.queues`) |
| `--concurrency / -c` | Concurrence Celery (défaut: `integration.yaml → xworker.concurrency`) |
| `--hostname / -n` | Nom du worker Celery (ex: `worker1@%h`) |

### `stop [api|celery|all]`

```bash
xcore worker stop              # arrête tout
xcore worker stop api
xcore worker stop celery
```

### `status`

```bash
xcore worker status
xcore worker status --json
```

Affiche un tableau avec PID, état et chemin de log pour chaque processus.

### `logs [api|celery|all]`

```bash
xcore worker logs                      # 50 dernières lignes de tout
xcore worker logs api -n 100
xcore worker logs celery --follow      # tail -f en temps réel
```

| Option | Description |
|:-------|:------------|
| `--lines / -n` | Nombre de lignes (défaut: 50) |
| `--follow / -f` | Suit en temps réel (cible unique uniquement) |

### `inspect`

Liste les tâches Celery enregistrées et les workers actifs.

```bash
xcore worker inspect
```

### `purge [queue]`

Vide une file d'attente Celery.

```bash
xcore worker purge              # vide la file "default"
xcore worker purge emails
```

### `beat`

Lance le scheduler Celery Beat.

```bash
xcore worker beat
xcore worker beat --detach
xcore worker beat --schedule /tmp/beat-schedule
```

### Fichiers générés

| Fichier | Description |
|:--------|:------------|
| `.xcore/pids/api.pid` | PID du processus uvicorn |
| `.xcore/pids/celery.pid` | PID du worker Celery |
| `.xcore/pids/beat.pid` | PID de Celery Beat |
| `log/api.log` | Logs uvicorn |
| `log/celery.log` | Logs Celery worker |
| `log/beat.log` | Logs Celery Beat |

---

## Options globales

| Option | Description |
|:-------|:------------|
| `--config <path>` | Chemin vers `integration.yaml` (défaut : auto-détection) |
| `--version` | Affiche la version (`xcore v2.1.3`) |
