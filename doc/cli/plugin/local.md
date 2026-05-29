---
title: Local Plugin Development
description: Scaffold, symlink, and iterate on plugins during local development.
icon: material/code-braces
---

# Local Plugin Development

The `plugin local` command group is designed to accelerate the development of new features.

## Scaffolding a New Plugin

Create a complete plugin structure with one command. The `scaffold` command supports flags to pre-configure your code.

```bash title="Trusted plugin with DB and cache"
xcli plugin local scaffold my_plugin \
  --mode trusted \
  --db \
  --cache
```

```bash title="Sandboxed plugin with scheduler"
xcli plugin local scaffold my_plugin \
  --mode sandboxed \
  --scheduler
```

### Scaffold Flags

| Flag | Description |
|------|-------------|
| `--mode` | `trusted` (default) or `sandboxed` |
| `--db` | Generate `models.py`, `repository.py`, and `schemas.py` |
| `--cache` | Inject the cache service and add `@cached` examples |
| `--scheduler` | Inject the scheduler with `@cron` and `@interval` examples |
| `--no-routes` | Skip generating FastAPI router code |

### Generated Structure

```text
plugins/my_plugin/
├── plugin.yaml
├── src/
│   ├── __init__.py
│   ├── main.py          # Plugin class with lifecycle hooks
│   ├── models.py        # SQLAlchemy models (--db)
│   ├── schemas.py       # Pydantic schemas (--db)
│   └── repository.py    # BaseAsyncRepository subclass (--db)
└── tests/
    └── test_my_plugin.py
```

A scaffolded `src/main.py` (with `--db --cache`):

```python title="src/main.py (scaffolded)" linenums="1"
from xcore.sdk import AutoMixin, action, ok, error, cached, require_service

class Plugin(AutoMixin):

    async def on_load(self) -> None:
        await super().on_load()
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.logger.info("my_plugin loaded")

    @action("ping")
    async def ping(self, payload: dict) -> dict:
        return ok(pong=True)

    @action("get_item")
    @require_service("db")
    @cached(ttl=300, key=lambda self, p: f"item:{p.get('id')}")
    async def get_item(self, payload: dict) -> dict:
        item_id = payload.get("id")
        if not item_id:
            return error("id is required", "missing_id")
        # TODO: implement fetch logic
        return ok(item={"id": item_id})
```

## Linking for Development

Instead of copying files, create a symbolic link from your source directory to the project's plugin folder. Changes are reflected immediately without re-linking.

```bash title="Link your local source"
xcli plugin local link \
  --path /home/user/projects/my_plugin \
  --name my_plugin

# Linked: ./plugins/my_plugin -> /home/user/projects/my_plugin
```

### Unlinking

When done developing or switching to a production install:

```bash
xcli plugin local unlink my_plugin
# Symlink removed. Plugin is no longer active.
```

## Listing Plugins

The `local list` command shows all plugins and identifies whether they are physically installed or symlinked:

```bash
xcli plugin local list

# Name              Type        Mode       Version
# ─────────────────────────────────────────────────
# auth_plugin       installed   trusted    2.1.0
# billing_engine    installed   trusted    1.0.3
# my_plugin         symlinked   trusted    dev
# sandbox_proc      installed   sandboxed  0.9.1
```

!!! tip "Hot Reload"
    Set `interval: 2` in `integration.yaml` and `debug: true` for automatic reload on file save during development:
    ```yaml
    plugins:
      interval: 2
    app:
      debug: true
    ```
