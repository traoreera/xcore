# disk_watcher.py

Le fichier `xcore/sandbox/sandbox/disk_watcher.py` applique des quotas disque par plugin sandboxed.

## API

- `current_size_bytes()`
- `current_size_mb()`
- `check(plugin_name)`
- `check_write(plugin_name, estimated_bytes=0)`
- `stats()`

## Exception

- `DiskQuotaExceeded`

## Exemple

```python
watcher = DiskWatcher(Path("plugins/a/data"), max_disk_mb=50)
watcher.check("plugin_a")
```

## Contribution

- Garder la vérification peu coûteuse en I/O.
- Harmoniser les messages d’erreur quota avec `supervisor.py`.
