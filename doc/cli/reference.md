# CLI Reference

A comprehensive list of all commands available in `xcorecli`.

## Global Commands

- `xcli init`: Initialize a new xcore project.
- `xcli upgrade`: Migrate `integration.yaml` to the latest schema.
- `xcli login`: Authorize this machine with the marketplace (device-code flow).
- `xcli install`: Shortcut for `xcli plugin install`.
- `xcli health`: Global health check of all configured services.
- `xcli services`: Show status and details of all system services (local
  runtime — not the marketplace catalog, see `xcli service` below).

## `config`  Credentials

- `config set <api-key|signing-key> <value>`: Store one credential in
  `~/.xcli/config.json` — the manual alternative to `xcli login` above.
- `config show`: Print whether each credential is set (masked).

Only these two keys exist — no arbitrary `integration.yaml` settings live
here, see [Configuration](getting-started/configuration.md) for that file.

## `manager`  Administration

- `manager start`: Start the FastAPI server (uvicorn).
- `manager stop`: Stop the detached API server.
- `manager top`: Full-screen live dashboard (resources + logs).
- `manager logs`: Stream and filter application logs.
- `manager resources`: Live resource usage per plugin.
- `manager metrics`: Application metrics snapshot.
- `manager services list`: List all services.
- `manager services reload`: Reconnect a service.
- `manager services unload`: Shutdown a service.

!!! info "Production deployment moved"
    `deploy` (init/list/status, SSH transfer, pre/post hooks) is no
    longer part of `xcorecli` — it's fully replaced by the standalone
    [`xcore-agent`](https://github.com/traoreera/xcore-agent) deployment
    agent.

---

## `plugin`  Lifecycle

- `plugin info`: Detailed local plugin report.
- `plugin health`: Health check of all installed plugins.
- `plugin remove`: Uninstall a plugin.
- `plugin install`: Install from marketplace/git/zip.
- `plugin versions`: List marketplace versions.

### `plugin local`  Development
- `local scaffold`: Create a new plugin from template.
- `local link`: Symlink a local directory.
- `local unlink`: Remove a symlink.
- `local list`: List all plugins with link type.

### `plugin marketplace`  Discovery
- `marketplace browse`: List published plugins (`--sort newest|downloads|rating`).
- `marketplace search`: Search by name or description.
- `marketplace info`: Pre-install details, including published versions.
- `marketplace mine`: List *your* plugins — public and private alike (needs
  an API key; `browse`/`search`/`info` above are public, no credentials).

No `rate` command — rating requires a full user session (JWT), not an API
key; rate plugins from the XCoreHub dashboard.

### `plugin security`  Signing & validation
- `security sign`: HMAC-sign a plugin (`plugin.sig`).
- `security verify`: Verify a plugin's signature.
- `security validate`: Validate plugin manifest(s); `--check-breaking`
  diffs IPC actions/events against a saved schema snapshot, `--save`
  updates that snapshot.

### `plugin update`  Maintenance
- `update check`: Check for new versions.
- `update apply`: Apply updates (--all, --dry-run).

### `plugin runtime`  Control
- `runtime load`: Activate a plugin.
- `runtime unload`: Deactivate a plugin.
- `runtime reload`: Restart a plugin.
- `runtime reload-all`: Restart every active plugin at once.
- `runtime status`: Show active plugins.
- `runtime call`: Invoke a plugin action directly (`--payload '{"k": "v"}'`).

## `sandbox`  Isolated Execution

Run a plugin in isolation and inspect its declared resource/network/
filesystem policy — none of these require the plugin to already be loaded
by a running instance.

- `sandbox run`: Launch a plugin sandboxed, keep it running (Ctrl+C to stop).
- `sandbox call`: Start sandboxed, call one action, print the result, stop.
- `sandbox limits`: Show resource limits from the manifest.
- `sandbox network`: Show the declared network policy.
- `sandbox fs`: Show the declared filesystem policy.

## `service`  Marketplace Extensions

Mirror of `plugin` for the separate `xservices` catalog — not to be
confused with `xcli services`/`xcli manager services` (local runtime).

- `service info`: Detailed local extension report.
- `service health`: Health check of all installed extensions.
- `service remove`: Uninstall an extension.
- `service install`: Install from marketplace.
- `service versions`: List marketplace versions.

### `service marketplace`  Discovery
- `marketplace browse`: List published extensions (`--sort newest|installs|rating`).
- `marketplace search`: Search by name or description.
- `marketplace info`: Pre-install details, including published versions.

## `worker`  Background Tasks

- `worker start`: Start a Celery worker.
- `worker beat`: Start the scheduler.
- `worker inspect`: List tasks and nodes.
- `worker purge`: Clear a task queue.

### `worker process`  Orchestration
- `process start`: Start multiple instances.
- `process stop`: Shutdown all workers.
- `process restart`: Restart all workers.
- `process status`: Table of running worker PIDs.
- `process logs`: Tail worker-specific logs.

## `migration`  Database

- `migration init`: Setup Alembic.
- `migration scan`: Preview discovered models.
- `migration backup`: Create a DB backup.
- `migration restore`: Restore from backup.
- `migration backups`: List available backups.
- `migration revision`: Create a new migration.
- `migration upgrade`: Apply migrations (--backup).
- `migration downgrade`: Rollback migrations.
- `migration current`: Show the database's current revision.
- `migration heads`: Show the migration chain's latest defined revision(s).
- `migration stamp`: Mark the DB at a revision without running scripts.
- `migration history`: Show migration list.
