# Plugins

A plugin in `install.yaml`/`manifest.json` is one of two kinds:

## Embedded

Its full code sits inside `plugins/<id>/` in the artifact, tarred/encrypted
with everything else.

- `PluginRef.sha256` is **required** and is the hash the agent re-verifies
  post-extraction.
- This is the default — simplest, self-contained, no extra network calls at
  deploy time.

## Source-based

`plugin.yaml` declares a `source: {url, ref, subdirectory}` block (typically
handed out by a marketplace/registry as a resolvable link).

- Only non-code metadata (`plugin.yaml`, `.env.template`) ships in the
  artifact; the actual code is fetched from `url` at `ref` via `git` during
  the pipeline's `resolve_plugins` stage, merged onto that metadata.
- `PluginRef.sha256` is **optional** here — the packer doesn't fetch external
  repos at build time, so it has nothing to hash unless pinned out of band.

!!! warning "Use a commit SHA for `ref`, not a branch or tag"

    Only a SHA is content-addressed, so it's the only form that makes a
    pinned `sha256` (or the absence of one) mean something — a mutable branch
    can change without the manifest ever noticing.

## Resolution mechanism

`PluginResolver` (`plugin_resolver.py`) fetches via:

```
git init + fetch --depth 1 <ref> + checkout FETCH_HEAD
```

This works for a branch, tag, or commit SHA alike (unlike `git clone
--branch`, which can't target an arbitrary commit). Public and private repos
are the same operation with different auth, exactly like using `git` from a
shell:

- **SSH** (`git@host:org/repo.git`) — authenticates via the host's own SSH
  agent/config; xcore-agent does nothing special.
- **HTTPS** — authenticates via a per-host token from `--git-token
  HOST=TOKEN` (repeatable, on `deploy`/`watch`), spliced into the URL as
  `https://x-access-token:<token>@host/...`. No token configured for that
  host just means the URL is used as-is (fine for a public repo).

## Plugins vs. extensions

| | Plugin | Extension (service) |
|---|---|---|
| Install target | `plugins/<id>/` (`Layout.plugin_dir`) | `extensions/<id>/` (`Layout.extension_dir`) |
| Metadata | `plugin.yaml` | none |
| `execution_mode: trusted` signing | Supported (`--plugin-secret-key`) | Not applicable |
| Marketplace kind | `--kind plugin` | `--kind service` |

A plugin and an extension may legitimately share an id — they install to
different target directories — which is why scaffolded step ids distinguish
them (`install_<id>` vs `install_ext_<id>`).

## Environment files

A plugin may declare an optional `environment:` block in `plugin.yaml`. The
`write_env` action (or `--env-template` at scaffold time) writes the required
variables to the plugin's env file and validates them before the plugin is
started. Missing required variables → a clear `InstallError`, not a silent
no-op.
