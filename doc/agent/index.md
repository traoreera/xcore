# xcore-agent

Deployment agent that takes a project from a Hub-hosted artifact to a running
set of plugins on a client's VPS, without ever needing `git` or shell access
on the target host. Two Hubs, two pipelines:

- **`deploy` / `pipeline.py`** — the originally-designed `.xdeploy` artifact:
  encrypted, Ed25519-signed, multi-plugin-per-project, fetched from a richer
  "XCore Hub" (see the [XCore Hub API contract](architecture.md) — still a
  *proposed*, unvalidated contract).
- **`deploy-marketplace` / `marketplace_pipeline.py`** — the **real**,
  already-running `xcore-team/marketplace` backend: plain HMAC-signed ZIPs,
  one plugin (or extension) per deployment, `X-API-Key` auth. See
  [the real xcore-team/marketplace API contract](marketplace.md) — this one is
  validated against the actual backend source, not inferred.

```
# .xdeploy (proposed Hub)
authenticate -> request_artifact -> download -> verify_signature ->
obtain_key -> decrypt -> extract -> verify_manifest -> validate_project ->
resolve_plugins -> resolve_sequence -> install -> healthcheck -> notify

# marketplace (real Hub)
fetch -> verify_signature (HMAC) -> extract -> load_plan (local file) ->
resolve_sequence -> install -> healthcheck
```

Each stage is enforced by an explicit state machine (`agent/state.py` and
`agent/marketplace_state.py` respectively) so neither pipeline can skip a
security-relevant step — e.g. it is structurally impossible to reach
`install` without a stage having verified the artifact's signature first.

On top of the `.xdeploy` pipeline, `Watcher` (`agent/watcher.py`) is the
CI/CD loop: poll a project's latest version/tag and redeploy automatically
when it changes, then run garbage collection so rollback snapshots and
cached downloads don't grow forever. `MarketplaceWatcher`
(`agent/marketplace_watcher.py`) is the same loop for the marketplace flow,
polling one plugin/extension slug via `MarketplaceClient.get_latest_version`
and redeploying through `MarketplaceDeploymentRunner`.

A third mechanism sits outside both pipelines — no artifact, no state
machine, no Hub of either kind: `resolve-sources`/`watch-sources`
(`resolve_sources.py`/`watch_sources.py`) resolve every `source:` a
project's *own* `install.yaml` declares (marketplace slug or git) directly
onto its `plugins/`/`extensions/` directories, in place. For a project
resolving its **own** sources against itself — typically a container image
reconstructing its marketplace-sourced plugins at boot
(`docker-entrypoint.sh`), before the app underneath ever loads them —
rather than for installing a Hub-hosted bundle onto a *different* host, which
is what `deploy`/`deploy-marketplace` are for. `watch-marketplace` cannot
substitute for `watch-sources` here: it replays the entire `install.yaml`
through one fetched artifact, which only works when the project being
deployed **is** a single marketplace plugin/extension, not when it merely
**depends on** several independent ones (see `watch_sources.py`'s module
docstring).

## What's real vs. stubbed today

| Component | Status |
|---|---|
| `install.yaml` / `manifest.json` schema (Pydantic, closed action enum) | Implemented, tested |
| `.xdeploy` packer (tar/zstd/AES-256-GCM/Ed25519) | Implemented, tested — `xcore_agent/packer/` |
| Ed25519 signature verification, AES-256-GCM decryption, zstd decompression | Implemented, tested |
| Tar extraction with path-traversal guarding | Implemented, tested |
| Content-hash re-verification post-extraction | Implemented, tested |
| Filesystem install / snapshot / rollback driver | Implemented, tested |
| CI/CD watch loop (`Watcher`: poll Hub, redeploy on version change) | Implemented, tested — `agent/watcher.py` |
| Garbage collector (stale snapshots + cached versions, forced restart) | Implemented, tested — `agent/gc.py` |
| `SystemdSupervisor` / `DockerSupervisor` / `KubernetesSupervisor` | Implemented, tested — `agent/systemd_supervisor.py`, `agent/docker_supervisor.py`, `agent/kubernetes_supervisor.py` |
| Provisioner registry (`provision` action) + `ShellCommandProvisioner` | Implemented, tested — see [Provisioning](provisioning.md) |
| Required environment variable validation (`write_env`) | Implemented, tested |
| CI (GitHub Actions: black/isort/flake8/mypy/pytest) | Implemented — `.github/workflows/ci.yml` |
| `HttpHubClient` (proposed REST contract) | Implemented, tested — see [XCore Hub API contract](architecture.md) |
| `MarketplaceClient` / `MarketplaceDeploymentRunner` | Implemented, tested against the **real, validated** `xcore-team/marketplace` API contract |
| Plugin resolution from a git repo | Implemented, tested against real local git repos — `plugin_resolver.py` |
| k8s supervisor | Implemented, tested — `agent/kubernetes_supervisor.py` |
| CI/CD watch loop for the marketplace flow | Implemented, tested — `agent/marketplace_watcher.py` |
| `install.yaml` scaffolding | Implemented, tested — `scaffold.py`, exposed as `init-plan` |
| In-place marketplace source resolution (`resolve-sources`/`watch-sources`) | Implemented, tested — `resolve_sources.py`, `watch_sources.py` |
| `.xdeploy` upload to a live Hub (`publish`) | Implemented, tested — `agent/hub_client.py::HttpHubClient.publish`; the *download* side (`deploy`/`watch`) still targets the proposed, not-yet-live Hub contract above |

`install.yaml` has **no generic "run a command" action** — every step is one
of a fixed, closed set (`prepare`, `provision`, `install_plugin`,
`configure_plugin`, `write_env`, `start`, `stop`, `restart`, `healthcheck`,
`rollback`, ...), validated by a discriminated Pydantic union before the
agent executes anything. A tampered or malicious artifact cannot turn
xcore-agent into an arbitrary remote-execution primitive.

## Project status

Version `0.1.0`. This project is under active development; the `.xdeploy` Hub
contract is still proposed, but the marketplace flow targets a real, running
backend.

## Documentation map

| Page | Contents |
|---|---|
| [Getting started](getting-started.md) | Installation and first commands |
| [CLI reference](usage.md) | Every `xcore-agent` command and option |
| [Architecture](architecture.md) | Layout, XCore Hub API contract |
| [Pipelines](pipelines.md) | The two deployment pipelines in detail |
| [Real marketplace flow](marketplace.md) | The validated marketplace contract |
| [Plugins](plugins.md) | Embedded vs. registry-resolved plugins |
| [Provisioning](provisioning.md) | The `provision` action |
| [Key custody](key-custody.md) | The key custody model |
| [API reference](https://traoreera.github.io/xcore-agent/api/pipeline/) | Auto-generated from docstrings — hosted on `xcore-agent`'s own docs site, not mirrored here (needs the package importable at build time) |
