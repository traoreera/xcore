# CLI reference

`xcore-agent` is a Typer application. Run `xcore-agent --help` for the full
list, or `xcore-agent <command> --help` for a command's options. Long-lived
credentials can be passed via environment variables (see
[Getting started](getting-started.md#environment-variables)) so they never
appear in the process list.

## Global options

| Option | Description |
|---|---|
| `--help` | Show help and exit |
| `--version` | Show the version and exit |

## `validate`

Validate an `install.yaml` (and optionally a `manifest.json`) — local only,
no network needed.

```
xcore-agent validate <install-yaml> [--manifest-json <path>]
```

| Argument / option | Description |
|---|---|
| `install-yaml` | Path to `install.yaml` |
| `--manifest-json` | Optional path to `manifest.json` to validate alongside it |

Output prints the step count and the resolved execution order.

## `init-plan`

Generate a starter `install.yaml` for a project. The result is validated
through `InstallPlan` before being written, so it is guaranteed loadable as-is.

```
xcore-agent init-plan <project-id> --plugin <id> [options]
```

| Argument / option | Description |
|---|---|
| `project-id` | `project_id` stamped in the plan — must equal the plugin's marketplace slug for `deploy-marketplace`/`watch-marketplace` |
| `--plugin` | Plugin id to install (repeatable) — one `install_plugin` step per id, in order given |
| `--extension` | Extension id to install (repeatable) — one `install_extension` step per id, separate namespace from `--plugin` |
| `--version` | Version to stamp in the plan (default `0.1.0`) |
| `--output` | Where to write the generated `install.yaml` (default `deployment/install.yaml`) |
| `--env-template` | `PLUGIN=RELATIVE_PATH` adding a `write_env` step (repeatable) |
| `--snapshot` | Take a rollback snapshot before each install step (default on) |
| `--healthcheck` | Append a `healthcheck` step after `start` (default on) |
| `--healthcheck-timeout` | Healthcheck timeout, e.g. `30s` or `2m` (default `30s`) |
| `--healthcheck-retries` | Healthcheck retry count (default 3) |
| `--force` | Overwrite `--output` if it already exists |

See [init-plan scaffolding](scaffold.md) for the generated plan shape.

## `build`

Build, encrypt, and sign a `.xdeploy` artifact from a project source tree.

```
xcore-agent build <source-root> --project-id <id> --project-name <name>
                 --version <ver> --output <path> [--signing-key-file <path>]
```

| Argument / option | Description |
|---|---|
| `source-root` | Project source tree: `plugins/`, `integration.yaml`, `deployment/install.yaml` |
| `--project-id` | Project id (`prj_...`) |
| `--project-name` | Project display name |
| `--version` | Version to stamp, e.g. `1.0.0` |
| `--output` | Output path for the encrypted `.xdeploy` artifact |
| `--signing-key-file` | Raw 32-byte Ed25519 private key. A throwaway key is generated (and **not** saved) if omitted |

The DEK (hex) and signer public key (hex) are printed to stdout — hand the
DEK to the Hub for storage and distribute the public key to agents. They are
never saved by the agent.

## `publish`

Build, encrypt, sign, **and upload** a `.xdeploy` artifact to XCore Hub in
one step — `build` alone only produces a local file (you'd have to hand the
DEK to the Hub yourself); this does that upload for you. The DEK never
touches disk, exactly like `deploy`/`watch` never persist one either.

```
xcore-agent publish <source-root> --project-id <id> --project-name <name>
                    --version <ver> --xdevkey <key>
                    [--hub-url <url>] [--output <path>] [--signing-key-file <path>]
```

| Argument / option | Environment | Description |
|---|---|---|
| `source-root` | | Project source tree: `plugins/`, `integration.yaml`, `deployment/install.yaml` |
| `--project-id` | `XCORE_PROJECT_ID` | Project id (`prj_...`) |
| `--project-name` | | Project display name |
| `--version` | | Version to stamp on this artifact, e.g. `1.0.0` |
| `--xdevkey` | `XCORE_XDEVKEY` | Project XDevKey — authenticates the upload to the Hub |
| `--hub-url` | `XCORE_HUB_URL` | Hub base URL (default `https://hub.xcorehub.dev`) |
| `--output` | | Also write the sealed artifact locally (optional — it stays on the Hub either way; this is just a copy for your own records) |
| `--signing-key-file` | | Same as `build --signing-key-file` — reuse the same key across every version of a project a `watch`er is told to follow, or it will reject the new signer |

Unlike `deploy`/`watch` below, this only needs the Hub's **upload** path
(`HttpHubClient.publish`) to work, not its download/authorize path — so it
is not affected by their "not available yet" caveat.

## `deploy`

Deploy a project version fetched from XCore Hub (the proposed `.xdeploy`
contract). Requires a live Hub API — currently fails at the `authenticate`
step by design, until the real Hub exists.

```
xcore-agent deploy --project-id <id> --version <ver>
        --xdevkey <key> --deployment-credential <cred>
        --project-root <path> --signer-public-key <path>
        [--hub-url <url>] [--git-token HOST=TOKEN]...
        [--provisioners-config <path>] [--plugin-secret-key <key>]
```

| Option | Environment | Description |
|---|---|---|
| `--project-id` | `XCORE_PROJECT_ID` | Project id (`prj_...`) |
| `--version` | | Version to deploy, e.g. `1.0.0` |
| `--xdevkey` | `XCORE_XDEVKEY` | Project XDevKey |
| `--deployment-credential` | `XCORE_DEPLOYMENT_KEY` | Deployment credential (authorizes DEK unwrap) |
| `--hub-url` | `XCORE_HUB_URL` | Hub base URL (default `https://hub.xcorehub.dev`) |
| `--project-root` | | Target install directory, e.g. `/etc/xcore/projects/my-erp` |
| `--signer-public-key` | | Path to the Hub's Ed25519 public key (raw 32 bytes) |
| `--git-token` | | `HOST=TOKEN` for a private git host a source-based plugin needs (repeatable) |
| `--marketplace-url` | `XCORE_MARKETPLACE_URL` | Marketplace root (no `/app/...` segment), used to resolve any plugin/extension whose `source:` is a marketplace slug (default `https://marketplace.xcorehub.dev`) — irrelevant if every plugin is embedded or git-sourced |
| `--marketplace-api-key` | `XCORE_MARKETPLACE_API_KEY` | `xdevkeys` API key (`xdk_...`), required only if some plugin/extension has a marketplace-slug `source:` (the default `xcli plugin install` records) |
| `--marketplace-signing-secret` | `XCORE_MARKETPLACE_SIGNING_SECRET` | HMAC signing secret verifying marketplace-sourced plugins/extensions — required alongside `--marketplace-api-key` whenever this project has one |
| `--provisioners-config` | | YAML mapping plugin id → `{command, env, timeout}` for the `provision` action |
| `--notifiers-config` | | YAML mapping event → `{command, env, timeout}` for the `notify` action |
| `--plugin-secret-key` | `XCORE_PLUGIN_SECRET` | Host's own `plugins.secret_key` — signs `execution_mode: trusted` plugins so this host's strict_trusted check can load them |

## `deploy-marketplace`

Deploy a single plugin or extension fetched from the real
`xcore-team/marketplace` backend — `X-API-Key` auth, HMAC-SHA256-signed plain
ZIP.

```
xcore-agent deploy-marketplace <slug> [--version latest] [--kind plugin|service]
        --api-key <key> --signing-secret <secret>
        --project-root <path> --install-plan <path>
        [--hub-url <url>] [--host-id <id>]
        [--provisioners-config <path>] [--plugin-secret-key <key>]
```

| Option | Environment | Description |
|---|---|---|
| `slug` | | Plugin or extension slug on the marketplace |
| `--version` | | Version to deploy, or `latest` (default `latest`) |
| `--kind` | | `plugin` (default) or `service` |
| `--api-key` | `XCORE_API_KEY` | `xdevkeys` API key (`xdk_...`) |
| `--signing-secret` | `XCORE_SIGNING_SECRET` | The publisher's HMAC signing secret — obtained out-of-band. See the trust-model caveat in [The real marketplace flow](marketplace.md) |
| `--hub-url` | `XCORE_HUB_URL` | Hub root **without** a plugin segment (default `https://marketplace.xcore.dev`) |
| `--project-root` | | Target install directory |
| `--host-id` | `XCORE_HOST_ID` | Host identifier reported with deployment status; defaults to hostname |
| `--install-plan` | | **Local** `install.yaml` — supplied by the operator, never fetched from the Hub |
| `--provisioners-config` | | YAML mapping plugin id → `{command, env, timeout}` for `provision` |
| `--plugin-secret-key` | `XCORE_PLUGIN_SECRET` | Same as `deploy --plugin-secret-key`; no effect for `kind=service` |

## `watch-marketplace`

The CI/CD loop for the marketplace flow — poll one slug and redeploy on
version change, then run garbage collection.

```
xcore-agent watch-marketplace <slug> [--kind plugin|service]
        --api-key <key> --signing-secret <secret>
        --project-root <path> --install-plan <path>
        [--interval 60] [--once] [--keep-snapshots 3]
        [--supervisor none|systemd|docker|kubernetes]
        [--systemd-user-scope] [--k8s-namespace <ns>] [--k8s-kubeconfig <path>] [--k8s-context <ctx>]
        [--provisioners-config <path>]
```

| Option | Environment | Description |
|---|---|---|
| `slug` | | Plugin or extension slug on the marketplace |
| `--kind` | | `plugin` (default) or `service` |
| `--api-key` | `XCORE_API_KEY` | `xdevkeys` API key (`xdk_...`) |
| `--signing-secret` | `XCORE_SIGNING_SECRET` | Publisher HMAC signing secret |
| `--hub-url` | `XCORE_HUB_URL` | Hub root (default `https://marketplace.xcore.dev`) |
| `--project-root` | | Target install directory |
| `--host-id` | `XCORE_HOST_ID` | Host identifier; defaults to hostname |
| `--install-plan` | | **Local** `install.yaml`, supplied by the operator |
| `--interval` | | Seconds between marketplace checks (default 60) |
| `--once` | | Check once and exit instead of looping forever |
| `--keep-snapshots` | | Rollback snapshots to keep for this plugin (default 3) |
| `--supervisor` | | How to restart the plugin after a redeploy and GC pass (`none`, `systemd`, `docker`, `kubernetes`) |
| `--systemd-user-scope` | | Use `systemctl --user` vs system-wide (default on) |
| `--k8s-namespace` | | Namespace for `--supervisor kubernetes` (default `default`) |
| `--k8s-kubeconfig` | | Path to a kubeconfig (defaults to kubectl's own) |
| `--k8s-context` | | kubeconfig context (defaults to kubectl's current) |
| `--provisioners-config` | | YAML mapping plugin id → `{command, env, timeout}` for `provision` |

## `watch`

The CI/CD loop for the `.xdeploy` flow — poll XCore Hub for a new
version/tag and redeploy automatically. Runs garbage collection after every
successful redeploy. Requires a live Hub API (not yet available).

```
xcore-agent watch --project-id <id> --xdevkey <key> --deployment-credential <cred>
        --project-root <path> --signer-public-key <path>
        [--interval 60] [--once] [--keep-snapshots 3]
        [--supervisor none|systemd|docker|kubernetes]
        [--systemd-user-scope] [--k8s-namespace <ns>] [--k8s-kubeconfig <path>] [--k8s-context <ctx>]
        [--git-token HOST=TOKEN]...
        [--marketplace-url <url>] [--marketplace-api-key <key>] [--marketplace-signing-secret <secret>]
        [--provisioners-config <path>] [--notifiers-config <path>]
```

Options match `deploy` (including `--marketplace-url`/`--marketplace-api-key`/
`--marketplace-signing-secret`/`--notifiers-config`, but not
`--plugin-secret-key`, which `watch` doesn't take) plus the loop controls
from `watch-marketplace` (`--interval`, `--once`, `--keep-snapshots`,
supervisor flags).

## `gc`

Purge stale rollback snapshots and cached artifact downloads; optionally
force every installed plugin to restart afterward.

```
xcore-agent gc --project-root <path> [--cache-root <path>]
        [--keep-version <ver>]... [--keep-snapshots 3]
        [--force-restart] [--supervisor systemd|docker|kubernetes]
        [--systemd-user-scope] [--k8s-namespace <ns>] [--k8s-kubeconfig <path>] [--k8s-context <ctx>]
```

| Option | Description |
|---|---|
| `--project-root` | Project root (extracted layout) |
| `--cache-root` | Cache root to prune (e.g. `~/.cache/xcore-agent/<project-id>`) |
| `--keep-version` | Version(s) to keep in the cache (repeatable) |
| `--keep-snapshots` | Rollback snapshots to keep per plugin (default 3) |
| `--force-restart` | Restart every installed plugin after cleanup |
| `--supervisor` | Which supervisor to use when `--force-restart` is set (default `systemd`) |
| `--systemd-user-scope` | Use `systemctl --user` vs system-wide (default on) |
| `--k8s-namespace` / `--k8s-kubeconfig` / `--k8s-context` | Kubernetes supervisor settings |

## `resolve-sources`

Resolve every `source:` declared in a project's own `install.yaml` directly
onto its `plugins/`/`extensions/` directories, in place — **no `.xdeploy`
artifact, no Hub, no Ed25519 signature involved at all**. Not affected by
`deploy`/`watch`'s Hub-download caveat above: this never touches the Hub,
only the marketplace's plain HMAC-signed ZIP endpoints (same ones
`deploy-marketplace`/`xcli plugin install` use).

For a project resolving its **own** sources against itself — typically a
container image reconstructing its marketplace-sourced plugins at boot
(`docker-entrypoint.sh`), before the app underneath ever loads them. See
`agent.pipeline.DeploymentRunner._resolve_plugins` for the
artifact-verifying equivalent used by `deploy`/`watch` instead.

```
xcore-agent resolve-sources <project-root> [--install-plan <path>]
        [--marketplace-url <url>] [--marketplace-api-key <key>]
        [--marketplace-signing-secret <secret>]
        [--git-token HOST=TOKEN]... [--cache-root <path>]
```

| Option | Environment | Description |
|---|---|---|
| `project-root` | | Project root containing `deployment/install.yaml` and its `plugins/`/`extensions/` |
| `--install-plan` | | Override path to `install.yaml` (default `<project-root>/deployment/install.yaml`) |
| `--marketplace-url` | `XCORE_MARKETPLACE_URL` | Marketplace root, used for any step whose `source:` is a marketplace slug (default `https://marketplace.xcorehub.dev`) |
| `--marketplace-api-key` | `XCORE_MARKETPLACE_API_KEY` | `xdevkeys` API key, required only if some step has a marketplace-slug `source:` |
| `--marketplace-signing-secret` | `XCORE_MARKETPLACE_SIGNING_SECRET` | HMAC signing secret verifying marketplace-sourced steps — required alongside `--marketplace-api-key` whenever this project has one |
| `--git-token` | | `HOST=TOKEN` for a private git host a source-based step may need (repeatable) — public repos and SSH URLs need none of this |
| `--cache-root` | | Resolver cache directory (default `~/.cache/xcore-agent/resolve-sources`) |

A step without a `source:` is assumed to already be present in the tree —
nothing to resolve for it. Prints each resolved `(kind, id) -> target`.

## `watch-sources`

Poll the marketplace for every `source:` declared in a project's own
`install.yaml` and re-resolve (in place) whichever ones have a newer
published version — the multi-source counterpart to `watch-marketplace` for
a project that **depends on** several independent marketplace plugins/
extensions, rather than **being** one itself. `watch-marketplace` replays
the *entire* `install.yaml` through a single fetched artifact, which breaks
the moment more than one step declares its own `source:` — see
`watch_sources.py`'s module docstring.

Like `resolve-sources`, this never touches `install.yaml`'s own
`start`/`healthcheck` steps and never restarts anything — see
`--exit-on-update` below for the intended way to let a supervisor do that.

```
xcore-agent watch-sources <project-root>
        --marketplace-api-key <key> --marketplace-signing-secret <secret>
        [--marketplace-url <url>] [--install-plan <path>]
        [--interval 300] [--once] [--exit-on-update] [--cache-root <path>]
```

| Option | Environment | Description |
|---|---|---|
| `project-root` | | Project root containing `deployment/install.yaml` and its `plugins/`/`extensions/` |
| `--marketplace-api-key` | `XCORE_MARKETPLACE_API_KEY` | `xdevkeys` API key — required (unlike `resolve-sources`, where it's optional) |
| `--marketplace-signing-secret` | `XCORE_MARKETPLACE_SIGNING_SECRET` | HMAC signing secret — required |
| `--marketplace-url` | `XCORE_MARKETPLACE_URL` | Marketplace root (default `https://marketplace.xcorehub.dev`) |
| `--install-plan` | | Override path to `install.yaml` (default `<project-root>/deployment/install.yaml`) |
| `--interval` | | Seconds between marketplace checks (default 300) |
| `--once` | | Check once and exit instead of looping forever |
| `--exit-on-update` | | Exit (code 0) right after applying at least one update instead of continuing to poll — for a process supervisor that restarts the whole process to pick up the newly-written files (this command never restarts anything itself). Ignored with `--once`, which always exits after its single check |
| `--cache-root` | | Resolver cache directory (default `~/.cache/xcore-agent/watch-sources`) |
