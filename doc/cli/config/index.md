# CLI Configuration

The `config` command group stores the two credentials `xcorecli` needs to
talk to the marketplace: an **API key** (`xdk_...`, authorizes downloads)
and a **signing key** (verifies the HMAC signature of every ZIP before
extraction). It does **not** manage `integration.yaml` or any other
project-level setting — see [Getting started → Configuration](../getting-started/configuration.md)
for that.

!!! tip "Prefer `xcli login`"
    `xcli login` (device-code flow, opens a browser) fetches and stores
    **both** credentials in one step, without ever printing them to the
    terminal. `config set` below is the manual fallback — useful in a
    non-interactive environment (CI, a container) where opening a browser
    isn't possible.

## Commands

| Command | Description |
|---------|-------------|
| `xcli config set <key> <value>` | Store a credential — `key` must be `api-key` or `signing-key`. |
| `xcli config show` | Print whether each credential is set (values are masked, never shown in full). |

## Setting credentials manually

```bash
xcli config set api-key xdk_...
xcli config set signing-key <your-signing-secret>
```

Both are written to `~/.xcli/config.json` — the same file `xcli login`
writes to, so mixing the two approaches (login once, then manually rotate
one key later) is safe.

## Checking status

```bash
xcli config show
```

```
api-key:     set
signing-key: not set
```

Nothing else is configurable through this command group — there is no
`get`/`validate` sub-command, and no arbitrary `key.path value` form; `key`
is restricted to exactly `api-key` or `signing-key`.
