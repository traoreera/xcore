# The real marketplace flow

Unlike the `.xdeploy` Hub contract (proposed, unvalidated — see
[Architecture](architecture.md)), this section describes the **real,
already-running `xcore-team/marketplace` backend**, read directly from its
source (`app/marketplace`, `app/xdevkeys`). It is a structurally different
contract, not just a different base URL, which is why it gets its own client
(`marketplace_client.py`) and pipeline (`marketplace_pipeline.py`) instead of
a second `HubClient` implementation:

| | Proposed `.xdeploy` Hub | Real xcore-team/marketplace |
|---|---|---|
| Auth | Login exchange → bearer token | Static `X-API-Key: xdk_...` header on every request |
| Unit of deployment | A "project" — many plugins, one manifest | One plugin *or* one extension ("service"), by marketplace slug |
| Artifact format | Encrypted (`.xdeploy`): tar → zstd → AES-256-GCM | Plain ZIP (GitHub's zipball API, unmodified) |
| Integrity/authenticity | Ed25519 signature over the ciphertext, verified against a distributed public key | `X-Signature: hmac_sha256:<hex>` over the ZIP bytes, verified against a **shared secret** |
| Deployment orchestration (`install.yaml`) | Bundled inside the artifact | **Not present in the artifact at all** — supplied locally by the operator |
| Deployment reporting | `POST /v1/deployments/report` | `POST /deployments/report` (`app/xdeployments`) — `X-API-Key` auth, best-effort, alongside the always-written local JSON report |

## Auth

`X-API-Key: xdk_...` (obtained via `POST /xdevkeys/api-keys` on the
marketplace) is sent on the one call that needs it (`fetch_artifact`).
`get_latest_version` reads the public plugin/service detail route, no key
needed.

## Endpoints

```
GET /plugins/{slug}                         (or /services/{slug} for an extension)
    <- {..., "latest_version": "1.2.3", ...}

GET /plugins/{slug}/install?version=latest  (or /services/{slug}/install)
    Header: X-API-Key: xdk_...
    <- raw ZIP bytes
       Header: X-Signature: hmac_sha256:<hex>
       Header: X-Plugin: name@version        (X-Service for an extension)
       Header: X-Repo: owner/repo@tag
```

## The HMAC signature is symmetric — read this before trusting it

Unlike Ed25519, whoever holds the signing secret can also *forge* a signature
with it, and the secret here is the plugin developer's own `xdevkeys` signing
secret — **not** a key the Marketplace publishes for third parties to verify
against. `MarketplaceDeploymentRunner` still checks it (it catches transport
corruption and accidental tampering, and the operator must have obtained the
secret from the developer to check it at all), but treat that check as "this
is the bytes the developer's key produced," not as a substitute for trusting
the Marketplace connection itself (TLS + your own API key) the way the
`.xdeploy` design's Ed25519 verification was meant to let you skip trusting
the transport. `--signing-secret` is deliberately a required CLI argument,
not something xcore-agent fetches on your behalf, so this trust decision
stays visible at the call site.

## Deployment orchestration is not in the artifact

A plain GitHub zipball has no `manifest.json` or `deployment/install.yaml` —
it's just the developer's repository. `deploy-marketplace --install-plan`
therefore points at a file on the *operator's own host*, exactly the same
trust boundary `--provisioners-config` already uses (see
[Provisioning](provisioning.md)): the artifact fetched from the Hub supplies
code, never deployment instructions. `MarketplaceDeploymentRunner` still
validates that `install_plan.project_id == slug` as a sanity check, but the
plan's actual steps are never trusted input — they're a local file the
operator wrote.

## Deployment status reporting

Every `deploy-marketplace` run — success, failure, or rollback — calls
`POST /deployments/report` (`X-API-Key` auth) after writing its local JSON
report, so the Marketplace can show which version is actually running where
(`GET /deployments/{kind}/{slug}/hosts` — a "fleet" view keyed by
`--host-id`, which defaults to this machine's hostname if not given).

This is intentionally **best-effort**: `MarketplaceClient.report_deployment`
can raise, but `MarketplaceDeploymentRunner` catches that itself and only
logs a warning — a Hub that's down or a key that's expired must never turn an
otherwise-successful (or otherwise-already-failed) deployment into a
different outcome. A deployment report is scoped to whoever's API key made
the call, not to the plugin's publisher — you don't need to own a plugin to
deploy it and track your own rollout of it.

## Plugins vs. services

- `--kind plugin` targets `GET /plugins/{slug}/install` — a plugin with a
  `plugin.yaml`, installed under `plugins/<id>/`.
- `--kind service` targets `GET /services/{slug}/install` — an extension (a
  shared non-plugin service), installed under `extensions/<id>/`. It has no
  `plugin.yaml`/`execution_mode`, so `--plugin-secret-key` has no effect.

## Testing

`tests/test_marketplace_client.py` and `tests/test_marketplace_pipeline.py`
exercise the whole flow end-to-end against `httpx.MockTransport`: a real
GitHub-zipball-shaped ZIP, real HMAC-SHA256 signing/verification, real
extraction (including the single-top-level-directory flattening GitHub's
zipball API requires) and path-traversal guarding, real install.yaml dispatch
and rollback — only the HTTP transport is faked.
