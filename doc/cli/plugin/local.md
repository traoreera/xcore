# Local Plugin Development

The `plugin local` command group is designed to accelerate the development of new features.

## Scaffolding a New Plugin

Create a new plugin structure with one command. The improved `scaffold` command supports several flags to pre-configure your code.

```bash title="Rich Scaffolding"
xcli plugin local scaffold my_plugin \
  --mode sandboxed \
  --db \
  --cache \
  --scheduler
```

### Scaffold Flags:
- `--mode`: `trusted` (default) or `sandboxed`.
- `--db`: Generates `models.py` and `schemas.py`.
- `--cache`: Injects the cache service into the plugin.
- `--scheduler`: Injects the scheduler service.
- `--no-routes`: Skips generating FastAPI router code.

## Linking for Development

Instead of installing a plugin, you can create a symbolic link from your development directory to the project's plugin folder. This allows you to see changes instantly.

```bash title="Link Plugin"
xcli plugin local link --path /path/to/your/source --name my-plugin
```

### Unlinking

When you're done developing or want to switch to a production version:

```bash
xcli plugin local unlink my-plugin
```

## Listing Plugins

The `local list` command shows all plugins and identifies whether they are **installed** (physical files) or **symlinked** (local development).

```bash
xcli plugin local list
```

!!! tip "Hot Reload"
    Ensure `debug: true` and a valid `interval` are set in your `integration.yaml` for the best development experience.
