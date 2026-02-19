# plugin_manifest.py

Le fichier `xcore/sandbox/contracts/plugin_manifest.py` charge et valide `plugin.yaml`/`plugin.json`.

## Rôle

- Parser typé via dataclasses
- Defaults par mode (`trusted`/`sandboxed`)
- Résolution variables d’environnement `${VAR}`
- Vérification compatibilité framework

## Sections principales

- `ExecutionMode`, `LogLevel`
- `ResourceConfig`, `RuntimeConfig`, `FilesystemConfig`
- `PluginManifest`
- `load_manifest(plugin_dir)`
- `check_framework_compatibility(...)`

## Champs importants

- `name`, `version`, `execution_mode`, `entry_point`
- `allowed_imports`, `resources`, `runtime`, `filesystem`, `env`
- `requires` (dépendances plugins)

## Exemple manifeste

```yaml
name: erp_core
version: "1.2.0"
execution_mode: sandboxed
framework_version: ">=1.0,<2.0"
entry_point: src/main.py
resources:
  timeout_seconds: 10
  max_memory_mb: 128
```

## Contribution

- Toute évolution du manifeste doit garder des defaults sûrs.
- Ajouter des validations strictes plutôt que des comportements implicites.
