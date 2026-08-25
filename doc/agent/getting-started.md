# Getting started

xcore-agent is a Python 3.12+ package distributed on PyPI. This guide walks
through installation and the first commands you will typically run.

## Installation

### With Poetry (recommended for development)

```bash
git clone https://github.com/traoreera/xcore-agent.git
cd xcore-agent
poetry install
```

### From PyPI

```bash
pip install xcore-agent
```

### Requirements

- Python >= 3.12, < 4.0
- For the `systemd` supervisor: a host with `systemctl`
- For the `docker` supervisor: the `docker` CLI
- For the `kubernetes` supervisor: the `kubectl` CLI and a reachable cluster

## Quick start

### 1. Validate an install plan

An `install.yaml` is the deployment plan that tells the agent *what* to run,
in what order. Validate one locally, with no network:

```bash
xcore-agent validate deployment/install.yaml --manifest-json manifest.json
```

The output prints the number of steps and their execution order.

### 2. Scaffold a starter plan

Generate a valid starter `install.yaml` — one `install_plugin` step per
`--plugin`, an optional `write_env` step per `--env-template`, then a `start`
and an optional `healthcheck`:

```bash
xcore-agent init-plan my-plugin \
  --plugin demo --env-template demo=plugins/demo/.env.template \
  --output deployment/install.yaml
```

The result is validated through the `InstallPlan` schema before being
written, so it is guaranteed loadable by `validate`, `deploy`, or
`deploy-marketplace` as-is.

### 3. Build a `.xdeploy` artifact

Bundle, encrypt, and sign a project source tree:

```bash
xcore-agent build ./my-project \
  --project-id prj_... --project-name my-erp --version 1.0.0 \
  --output ./my-erp-1.0.0.xdeploy.enc
```

The artifact is tarred, compressed with zstd, encrypted with AES-256-GCM
under a per-version data-encryption key (DEK), and signed with Ed25519. The
DEK and signer public key are printed to stdout for you to distribute — the
agent never stores them.

!!! warning "Throwaway keys"

    If `--signing-key-file` is omitted, a throwaway Ed25519 key is generated
    and **not saved** — fine for local testing, not for anything an agent
    needs to trust across builds.

### 4. Deploy from the real marketplace

The marketplace flow targets the already-running `xcore-team/marketplace`
backend. It deploys one plugin *or* extension by slug, with `X-API-Key`
auth and HMAC-SHA256 signature verification:

```bash
xcore-agent deploy-marketplace my-plugin \
  --version latest --kind plugin \
  --api-key xdk_... --signing-secret <the-developer's-hmac-secret> \
  --hub-url https://marketplace.example.com/app/marketplace \
  --project-root /etc/xcore/projects/my-erp \
  --install-plan ./deployment/install.yaml
```

Unlike the `.xdeploy` flow, the install plan is **not** inside the artifact —
the marketplace ships plain plugin source (a ZIP), so you supply the plan
locally with `--install-plan`. See [The real marketplace flow](marketplace.md).

### 5. Watch and redeploy automatically

Poll a Hub (either contract) for new versions and redeploy when one appears,
then run garbage collection:

```bash
# .xdeploy flow
xcore-agent watch \
  --project-id prj_... --xdevkey xdev_... --deployment-credential xdpk_... \
  --project-root /etc/xcore/projects/my-erp \
  --signer-public-key ./hub_signing.pub \
  --interval 60 --supervisor systemd

# marketplace flow
xcore-agent watch-marketplace my-plugin \
  --kind plugin \
  --api-key xdk_... --signing-secret <secret> \
  --hub-url https://marketplace.example.com/app/marketplace \
  --project-root /etc/xcore/projects/my-erp \
  --install-plan ./deployment/install.yaml \
  --interval 60 --supervisor systemd
```

Add `--once` to check a single time and exit instead of looping forever.

### 6. Garbage collection

Purge stale rollback snapshots and cached artifact downloads; optionally
force every plugin to restart afterward so no running process keeps serving
reclaimed state:

```bash
xcore-agent gc \
  --project-root /etc/xcore/projects/my-erp \
  --cache-root ~/.cache/xcore-agent/prj_... \
  --keep-version 1.0.0 --force-restart --supervisor docker
```

## Environment variables

Long-lived credentials can be supplied via environment variables instead of
CLI options, so they never appear in your shell history or process list:

| Variable | Command(s) | Purpose |
|---|---|---|
| `XCORE_PROJECT_ID` | `deploy`, `watch` | Project id (`prj_...`) |
| `XCORE_XDEVKEY` | `deploy`, `watch` | Project XDevKey |
| `XCORE_DEPLOYMENT_KEY` | `deploy`, `watch` | Deployment credential (DEK unwrap authorization) |
| `XCORE_HUB_URL` | `deploy`, `deploy-marketplace`, `watch`, `watch-marketplace` | Hub base URL |
| `XCORE_API_KEY` | `deploy-marketplace`, `watch-marketplace` | `xdevkeys` API key (`xdk_...`) |
| `XCORE_SIGNING_SECRET` | `deploy-marketplace`, `watch-marketplace` | Publisher HMAC signing secret |
| `XCORE_HOST_ID` | `deploy-marketplace`, `watch-marketplace` | Host identifier reported to the Hub |
| `XCORE_PLUGIN_SECRET` | `deploy`, `deploy-marketplace` | Host-local `plugins.secret_key` |

## Tests

```bash
poetry install --with dev
poetry run pytest -v
```

`tests/test_pipeline.py` and `tests/test_watcher.py` run the full `.xdeploy`
pipeline and CI/CD loop end-to-end (build via the real packer, sign, encrypt,
download via a fake Hub, verify, decrypt, decompress, extract, install,
persist state, garbage-collect, roll back on failure) without any network
access. `tests/test_marketplace_client.py` and
`tests/test_marketplace_pipeline.py` do the same for the marketplace flow —
only the HTTP transport is faked (`httpx.MockTransport`).

## Next steps

- Browse the [CLI reference](usage.md) for every command.
- Understand [how the pipelines work](pipelines.md).
- Read about [the real marketplace contract](marketplace.md).
