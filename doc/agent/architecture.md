# Architecture

## Layout

```
xcore_agent/
├── schema/
│   ├── install.py          # install.yaml — steps, action whitelist, dependency graph
│   └── manifest.py         # manifest.json — project/plugin metadata + content hash
├── packer/
│   └── builder.py          # build_artifact() — tar/zstd/encrypt/sign a project into .xdeploy
├── agent/
│   ├── state.py             # DeploymentState + allowed transitions
│   ├── errors.py
│   ├── hub_client.py        # HubClient protocol + HttpHubClient (proposed REST contract)
│   ├── install_driver.py    # filesystem install/snapshot/rollback + Supervisor/Provisioner protocols
│   ├── systemd_supervisor.py # Supervisor backed by `systemctl`
│   ├── docker_supervisor.py # Supervisor backed by the `docker` CLI
│   ├── kubernetes_supervisor.py # Supervisor backed by the `kubectl` CLI (Deployments)
│   ├── pipeline.py          # DeploymentRunner — one deployment, start to finish
│   ├── watcher.py           # Watcher — CI/CD loop: poll Hub, redeploy on version change
│   ├── gc.py                # GarbageCollector — prune snapshots/cache, force plugin restarts
│   ├── provisioners.py      # ShellCommandProvisioner + config loader for 'provision'
│   └── state_store.py       # tracks which version is currently installed
├── plugin_resolver.py        # PluginResolver — fetches a PluginSource plugin from git
├── crypto.py                 # signature verification, AES-GCM, content digest
├── scaffold.py               # scaffold_install_plan() — generates a starter install.yaml
└── cli.py                    # validate / init-plan / build / deploy / watch / gc
```

## The two contracts

The project speaks to two structurally different Hubs, so it carries two
clients and two pipelines rather than one abstraction forced to fit both:

| | `.xdeploy` Hub | Real xcore-team/marketplace |
|---|---|---|
| Client | `agent/hub_client.py` → `HubClient` protocol + `HttpHubClient` | `agent/marketplace_client.py` → `MarketplaceClient` |
| Pipeline | `agent/pipeline.py` → `DeploymentRunner` | `agent/marketplace_pipeline.py` → `MarketplaceDeploymentRunner` |
| Watch loop | `agent/watcher.py` → `Watcher` | `agent/marketplace_watcher.py` → `MarketplaceWatcher` |
| Status | **Proposed** REST contract, not yet built | **Real, validated** backend |
| Artifact | Encrypted `.xdeploy` (tar → zstd → AES-256-GCM, Ed25519-signed) | Plain ZIP (GitHub zipball), HMAC-SHA256-signed |
| Orchestration | `install.yaml` bundled inside the artifact | `install.yaml` supplied locally by the operator |

Everything else — the install driver, supervisors, provisioners, state store,
garbage collector, schemas — is shared between the two flows.

## Dependencies

- **pydantic** — `install.yaml`/`manifest.json` schemas, validated before
  anything executes
- **httpx** — async HTTP for both Hub clients (tests swap in
  `httpx.MockTransport`)
- **cryptography** — Ed25519, AES-256-GCM, content digests
- **zstandard** — `.xdeploy` compression
- **typer + rich** — CLI and console output
- **pyyaml** — plan/config parsing

## XCore Hub API contract (proposed, not validated)

XCore Hub doesn't exist yet, so `HttpHubClient` is implemented against a
REST contract *inferred* from this project's architecture notes rather than
a published spec. It's a concrete, working starting point — build the real
Hub against these routes, or edit `hub_client.py` once the real ones are
decided. Nothing else in xcore-agent needs to change either way: the
pipeline, watcher, and CLI all depend on the `HubClient` protocol, not on
this implementation.

All bodies are JSON; binary fields (`signature`, `signer_public_key`, `dek`,
`artifact_signature`) are base64; auth is `Authorization: Bearer <access_token>`
except on `/v1/auth` itself.

```
POST /v1/auth
    -> {xdevkey, project_id}
    <- {access_token}

GET /v1/projects/{project_id}/versions/latest
    <- {version}

GET /v1/projects/{project_id}/artifacts/{version}
    <- {download_url, signature, signer_public_key}

GET <download_url>                    (may be a different host — e.g. signed
    <- raw bytes                        blob storage — not necessarily the Hub)

POST /v1/deployments/authorize
    -> {deployment_credential, artifact_signature}
    <- {dek}                            (access revocation is enforced here)

POST /v1/deployments/report
    -> {project_id, deployment_id, status, version, started_at,
        completed_at, plugins}
    <- {deployment_id}
```

A 401/403 from `/v1/auth` or `/v1/deployments/authorize` raises
`AuthenticationError`; any other non-2xx raises `ArtifactError` (or
`DeploymentError` for `/v1/auth` and `/v1/deployments/report`) with the
status code and the response's `error` field, if present, in the message.
`tests/test_http_hub_client.py` exercises all of this against
`httpx.MockTransport` — no network, no real Hub needed to verify the client
speaks its own contract correctly.

See [The real marketplace flow](marketplace.md) for the contrast with the
validated marketplace contract.
