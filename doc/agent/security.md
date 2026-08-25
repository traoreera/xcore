# State machines & security

xcore-agent is designed so that **security-relevant steps cannot be skipped**,
even by a bug. This page collects the mechanisms that enforce that, and the
threat model they assume.

## Closed action whitelist

`install.yaml` has **no generic "run a command" action**. Every step is one
of a fixed, closed set (`prepare`, `provision`, `install_plugin`,
`install_extension`, `configure_plugin`, `write_env`, `start`, `stop`,
`restart`, `healthcheck`, `rollback`, ...), validated by a discriminated
Pydantic union (`schema/install.py`) before the agent executes anything.

A tampered or malicious artifact therefore **cannot** turn xcore-agent into
an arbitrary remote-execution primitive. The only shell-out mechanism is
`provision`, and it is deliberately not driven by the artifact — see
[Provisioning](provisioning.md).

## State machines

Each pipeline is driven by an explicit, closed transition table:

- `.xdeploy`: `agent/state.py` — `TRANSITIONS`
- marketplace: `agent/marketplace_state.py` — `MARKETPLACE_TRANSITIONS`

`DeploymentRunner._transition` / `MarketplaceDeploymentRunner._transition`
raise if a stage tries to move anywhere that isn't an allowed successor. The
consequence is structural: it is **impossible** to reach `install` without a
stage having verified the artifact's signature first. Terminal states are
`SUCCEEDED`, `FAILED`, and `ROLLED_BACK`.

## Signature verification before key use

In the `.xdeploy` pipeline, `verify_signature` (Ed25519) runs before
`obtain_key`/`decrypt`. In the marketplace pipeline, `verify_signature`
(HMAC-SHA256) runs immediately after `fetch`. In both, a failed verification
transitions to `failed` and the artifact never reaches extraction.

## Content integrity

- **Post-extraction re-verification**: the manifest carries a content hash;
  after extraction the agent re-hashes the installed tree and compares
  (`DeploymentRunner._verify_manifest`). Extraction can't silently substitute
  files.
- **Path-traversal guarding**: both tar extraction (`pipeline._safe_extract`)
  and ZIP extraction (`marketplace_pipeline._safe_extract_zip`) reject paths
  that escape the extraction root.
- **`PluginRef.sha256`**: embedded plugins are re-hashed after install.

## Trust boundaries

| Input | Trusted? | Why |
|---|---|---|
| Artifact bytes from the Hub | Untrusted until verified | Ed25519 (`.xdeploy`) or HMAC (marketplace) signature checked first |
| `install.yaml` inside a `.xdeploy` | Part of the signed artifact | Signed by the project publisher |
| `install.yaml` for marketplace | Operator-supplied local file | The marketplace ships plain source, never deployment instructions |
| `provision` command | Operator-supplied local config | `--provisioners-config`, never from the artifact |
| Git tokens, API keys, signing secrets | Operator-supplied | Passed at the CLI/env, never fetched or stored by the agent |

## Key custody

xcore-agent never generates or stores long-lived secrets. The artifact's
per-version DEK is obtained at deploy time from the Hub and kept only in
memory for the duration of one deployment. The XDevKey authenticates the
*project*; a separate deployment credential authorizes *this deployment* to
have the DEK unwrapped — a leaked XDevKey does not, by itself, grant artifact
decryption. See [Key custody](key-custody.md).

## The HMAC trust caveat

The marketplace signature is HMAC-SHA256 over the ZIP bytes with the plugin
developer's own `xdevkeys` signing secret — a **symmetric** secret, meaning
whoever holds it can also *forge* a signature. `--signing-secret` is
deliberately a required CLI argument, not something the agent fetches on your
behalf, so this trust decision stays visible at the call site. The HMAC check
catches transport corruption and accidental tampering, but it is **not** a
substitute for trusting the marketplace connection itself (TLS + your own API
key). See [The real marketplace flow](marketplace.md).
