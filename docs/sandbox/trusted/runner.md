# runner.py (TrustedRunner)

Le fichier `xcore/sandbox/trusted/runner.py` charge les plugins trusted en mémoire (même process que l’app).

## Responsabilités

- Import dynamique de l’entrypoint plugin
- Instanciation plugin + injection services
- Hooks lifecycle (`on_load`, `on_unload`, `on_reload`)
- Appel `handle` avec timeout
- Vérification accès filesystem (`check_filesystem_access`)

## Exceptions

- `TrustedLoadError`
- `FilesystemViolation`

## Exemple

```python
runner = TrustedRunner(manifest, services={"db": db})
await runner.load()
res = await runner.call("ping", {})
```

## Contribution

- Préserver la compatibilité duck-typing (pas d’héritage obligatoire).
- Nettoyer `sys.modules`/`sys.path` proprement au unload.
