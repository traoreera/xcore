# init-plan scaffolding

`init-plan` generates a starter `install.yaml` so you don't hand-derive the
same shape every time — and don't have to get every step id, `depends_on`
edge, and the closed `action` enum right by hand.

Hand-writing an `install.yaml` means re-deriving the same shape (`prepare`
→ one `install_plugin` per plugin → optional `write_env` → `start` →
optional `healthcheck`). `scaffold_install_plan` (`xcore_agent/scaffold.py`)
builds that shape as a plain dict — the same shape a human would hand-write —
and validates it through `InstallPlan.model_validate` before it's ever
written to disk, so a scaffolded plan is **guaranteed loadable** by
`validate`/`deploy`/`deploy-marketplace` as-is.

## Basic example

```bash
xcore-agent init-plan my-plugin \
  --plugin demo \
  --env-template demo=plugins/demo/.env.template \
  --output deployment/install.yaml
```

Produces approximately:

```yaml
format_version: "1"
project_id: my-plugin
version: 0.1.0
steps:
  - id: prepare
    action: prepare
  - id: install_demo
    action: install_plugin
    plugin: demo
    snapshot: true
  - id: write_env_demo
    action: write_env
    plugin: demo
    from: plugins/demo/.env.template
    depends_on: [install_demo]
  - id: start
    action: start
    depends_on: [write_env_demo]
  - id: healthcheck
    action: healthcheck
    depends_on: [start]
    timeout: 30s
    retries: 3
```

## What each option controls

| Option | Effect |
|---|---|
| `--plugin <id>` (repeatable) | One `install_plugin` step per id, in the order given |
| `--extension <id>` (repeatable) | One `install_extension` step per id; separate id namespace from `--plugin` (a plugin and an extension may share an id) |
| `--env-template PLUGIN=PATH` (repeatable) | Adds a `write_env` step for that plugin, copying `PATH` to the plugin's env file |
| `--snapshot` / `--no-snapshot` | Take a rollback snapshot before each install step (default on) |
| `--healthcheck` / `--no-healthcheck` | Append a `healthcheck` step after `start` (default on) |
| `--healthcheck-timeout` | e.g. `30s` or `2m` (default `30s`) |
| `--healthcheck-retries` | Retry count (default 3) |
| `--force` | Overwrite `--output` if it already exists |

## Step id naming

- Plugin install steps are named `install_<plugin-id>`.
- Extension install steps are named `install_ext_<extension-id>` — a plugin
  and an extension can legitimately share an id (they install to different
  target directories, see `Layout.plugin_dir` vs `Layout.extension_dir`), and
  step ids must stay unique across the whole plan (`InstallPlan._validate_graph`).

## Validation guarantees

- At least one plugin is required (`ValueError` otherwise).
- `--env-template` references must be known plugins — unknown ids raise a
  `BadParameter`.
- The plan is run through `InstallPlan.model_validate` before being written,
  so any inconsistency in the scaffolding logic surfaces as a `ValidationError`
  instead of a broken `install.yaml`.

## Hand-editing afterwards

A scaffolded plan is a starting point, **not a substitute for reviewing what
actually gets deployed**. Add `configure_plugin`, `provision`, `stop`,
`restart`, or `rollback` steps by hand, and re-run `validate` to confirm the
graph still resolves:

```bash
xcore-agent validate deployment/install.yaml
```

See the [schema reference](https://traoreera.github.io/xcore-agent/api/schema/) for the full step/action model.
