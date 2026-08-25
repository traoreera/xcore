# Plugin Security & Signing

Security is a core pillar of the `xcore` plugin system. We provide tools to ensure that only verified and safe code runs in your environment.

## Signing Plugins

For production use, plugins should be signed to prevent tampering. Signing uses an HMAC-SHA256 hash based on the plugin's content and a secret key.

```bash title="Sign Plugin"
xcli plugin security sign my-plugin --key "your-secret-signing-key"
```

This creates a `plugin.sig` file within the plugin directory.

!!! note "Secret Key Management"
    The `plugins.secret_key` in your `integration.yaml` must match the key used for signing for verification to succeed.

## Verification & Health

You can manually verify the integrity of a plugin:

```bash
xcli plugin security verify my-plugin
```

For a comprehensive check of all plugins (including manifest validation and AST analysis), use:

```bash
xcli plugin health
```

## Validating Manifests

Beyond signature checks, `validate` checks the plugin manifest itself
(`plugin.yaml` structure, required fields) and can track its **IPC
surface** — the actions and events a plugin exposes to others — across
versions:

```bash title="Validate a plugin"
xcli plugin security validate my-plugin
```

Without a path, it scans every plugin found via `integration.yaml`
instead of just one:

```bash
xcli plugin security validate
```

```bash title="Track breaking IPC changes"
xcli plugin security validate my-plugin --save            # snapshot today's IPC surface
xcli plugin security validate my-plugin --check-breaking   # diff against that snapshot
```

`--save` writes the current IPC action/event schemas to a snapshot file
(default `.xcore/schemas.json`, override with `--schema-file`); a later
`--check-breaking` run reports anything removed or changed since — useful
in CI to catch an accidental breaking change to a plugin's public IPC
contract before it ships.

## Strict Mode

Enable `strict_trusted` in your configuration to refuse any plugin that is not properly signed.

```yaml
plugins:
  strict_trusted: true
```

## AST Whitelisting

For **Sandboxed Plugins**, `xcore` uses an Abstract Syntax Tree (AST) analyzer to restrict imports.

- **Allowed**: `json`, `math`, `fastapi`, etc.
- **Forbidden**: `os`, `subprocess`, `shutil`, etc.

This prevents plugins from performing unauthorized filesystem or system operations.

!!! tip "Customizing Whitelists"
    Modify the `security.allowed_imports` section in `integration.yaml` to suit your project's needs.
