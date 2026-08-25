# Provisioning backing services

A plugin can declare a `provision` step in `install.yaml` for setting up a
backing service it needs — a database, a message queue, whatever.
xcore-agent deliberately ships **no** database/queue client to support this:
a lean deployment agent shouldn't carry backend-specific dependencies most
projects don't need. Instead, `provision` runs an **operator-configured shell
command**:

```yaml
# provisioners.yaml, passed via --provisioners-config on deploy/watch
demo:
  command: ["/usr/local/bin/provision-demo-schema.sh"]
  env:
    PGHOST: localhost
  timeout: 120   # seconds, default 300
```

## How it's invoked

1. The `provision` step in `install.yaml` references a plugin id
   (`ProvisionStep`).
2. The agent looks up that id in `--provisioners-config` (loaded by
   `load_provisioners_from_config` in `agent/provisioners.py`).
3. It appends the plugin id as the command's last argument and exports it as
   `PROVISION_PLUGIN_ID`.
4. It runs the command with the configured `env` and `timeout` (default 300s).

## Why this is safe to shell out to

Unlike anything inside `install.yaml` itself, the command comes from the
*operator's own trusted host-side config*, **never from the (untrusted)
`.xdeploy` artifact**, which only ever supplies a plugin id via
`ProvisionStep`. The operator already has root on their own VPS; nothing here
hands the artifact a new capability.

## Required config

No config passed to `provision` for a plugin that has one → a clear
`InstallError`, **not** a silent no-op.

## Trust boundary

`--provisioners-config` shares its trust model with the marketplace's
`--install-plan`: it's a local operator file. The artifact fetched from the
Hub supplies code, never deployment instructions or shell commands.
