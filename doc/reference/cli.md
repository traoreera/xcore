# CLI Reference

The `xcore` CLI exposes commands for managing plugins, the sandbox, marketplace, services, and worker processes.

```bash
poetry run xcore --help
poetry run xcore <command> --help
```

---

## Plugin Commands

```bash
xcore plugin list                          # List all discovered plugins and their status
xcore plugin info <name>                   # Show details for a specific plugin
xcore plugin reload <name>                 # Hot-reload a plugin
xcore plugin load <name>                   # Load a new plugin at runtime
xcore plugin unload <name>                 # Unload a running plugin
xcore plugin sign <path> --secret <key>    # Sign a plugin (creates plugin.sig)
xcore plugin verify <path> --secret <key>  # Verify a plugin signature
xcore plugin health                        # Validate all plugin manifests + AST
```

### `plugin list` output

```
NAME            VERSION  MODE       STATUS
auth_plugin     1.2.0    trusted    READY
billing_plugin  0.9.1    trusted    READY
analytics       1.0.0    sandboxed  READY
```

---

## Worker Commands (Celery)

```bash
xcore worker start celery                  # Start a Celery worker
xcore worker start celery --concurrency 8  # Start with custom concurrency
xcore worker beat                          # Start Celery beat (periodic tasks)
xcore worker inspect                       # Inspect active workers and their tasks
```

The worker reads configuration from `integration.yaml → services.xworker`. The Celery app bootstraps at module import time so `celery -A xcore.services.xworker.xworker worker` also works.

---

## Sandbox Commands

```bash
xcore sandbox scan <path>                  # AST-scan a plugin for forbidden imports
xcore sandbox test <name>                  # Run a sandboxed plugin in test mode
```

---

## Marketplace Commands

```bash
xcore marketplace search <query>           # Search for plugins on the marketplace
xcore marketplace install <plugin>         # Download and install a plugin
xcore marketplace info <plugin>            # Show marketplace plugin details
```

---

## Make Targets

The project `makefile` provides shorthand targets for common tasks:

| Target | Description |
|:-------|:-----------|
| `make dev` | Start with auto-reload (port 8000) |
| `make st` | Start in production mode |
| `make test` | Run the full test suite with coverage |
| `make benchmark` | Run performance benchmarks |
| `make lint-fix` | Auto-format with black, isort, autopep8, autoflake |
| `make lint-check` | Check formatting without modifying files |
| `make auto-security` | Run Bandit audit (output in `./reports/`) |
| `make clean` | Remove `__pycache__` and `.pyc` files |
| `make build` | clean + install + lint-fix |
| `make build-prod` | build + test + security-check |
| `make logs-live` | Tail `log/app.log` in real time |
| `make logs-error` | Show ERROR entries from the log |
| `make logs-search TERM="..."` | Search the log file |
| `make logs-stats` | Count log entries by level |
| `make add-plugin PLUGIN_NAME=x PLUGIN_REPO=url` | Clone a plugin from git |
| `make rm-plugin PLUGIN_NAME=x` | Remove a plugin directory |
