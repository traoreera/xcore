---
title: Plugin Security & Signing
description: Sign, verify, and audit plugins using HMAC signatures and AST analysis.
icon: material/shield-key
---

# Plugin Security & Signing

Security is a core pillar of the `xcore` plugin system. Xcore provides tools to ensure that only verified and safe code runs in your environment.

## Signing Plugins

For production use, sign plugins to prevent unauthorized modification. Signing generates an HMAC-SHA256 hash of the manifest and all source files.

```bash title="Sign a plugin"
xcli plugin security sign my-plugin --key "your-secret-signing-key"
# Computing HMAC-SHA256 of plugin content...
# plugin.sig written to ./plugins/my-plugin/plugin.sig
# Signature: a3f8c9...
```

This creates a `plugin.sig` file in the plugin directory. The signature covers:

- `plugin.yaml` manifest
- All `.py` files in `src/`
- `requirements.txt` (if present)

!!! note "Key Management"
    The `plugins.secret_key` in `integration.yaml` must match the key used during signing. Rotate both together if the key is compromised.

## Verification

Manually verify the integrity of a plugin:

```bash
xcli plugin security verify my-plugin

# Verifying 'my-plugin'...
# Files hashed: 4
# Signature match: OK
# Manifest valid: OK
```

For a comprehensive check of all installed plugins (manifest validation, signatures, and AST analysis for sandboxed plugins):

```bash
xcli plugin health

# Plugin Health Report
# ───────────────────────────────────────────────────
#  auth_plugin       OK       signed, manifest valid
#  billing_engine    WARNING  plugin.sig missing
#  text_transform    OK       sandboxed, AST clean
# ───────────────────────────────────────────────────
```

## Strict Mode

Enable `strict_trusted` in `integration.yaml` to refuse any unsigned plugin at boot time:

```yaml title="integration.yaml (production)"
plugins:
  strict_trusted: true
  secret_key: "${XCORE_PLUGINS_KEY}"
```

When enabled, Xcore will log and skip any trusted plugin missing a valid `plugin.sig`:

```text
WARN  [kernel] Skipping my-plugin: strict_trusted enabled and plugin.sig is absent.
```

## AST Import Whitelisting

For **Sandboxed Plugins**, Xcore uses an Abstract Syntax Tree (AST) analyzer to restrict imports before execution.

```bash title="Run AST scan manually"
xcli plugin security scan my-sandboxed-plugin

# AST Scan Report
# ──────────────────────────────────────────────────
#  Import          Status
#  ──────────────────────────────────────────────────
#  json            ALLOWED
#  math            ALLOWED
#  datetime        ALLOWED
#  os              BLOCKED
#  subprocess      BLOCKED (not in allowed_imports)
# ──────────────────────────────────────────────────
# Result: FAIL (1 forbidden import)
```

Customize the whitelist in `integration.yaml`:

```yaml
security:
  allowed_imports:
    - json
    - math
    - datetime
    - pydantic
    - fastapi
  forbidden_imports:
    - os
    - subprocess
    - socket
    - shutil
```

## Signing Workflow (Production)

Typical signing process before deploying a plugin:

```bash
# 1. Verify the plugin passes health checks
xcli plugin health

# 2. Sign the plugin
xcli plugin security sign billing_engine \
  --key "${XCORE_PLUGINS_KEY}"

# 3. Verify the signature is valid
xcli plugin security verify billing_engine

# 4. Deploy and confirm it loads correctly
xcli plugin runtime reload billing_engine
xcli plugin runtime status
```

## See Also

[Security Architecture](../../security/security.md)
:   Deep dive into AST scanning and the FilesystemGuard.

[Execution Modes](../../kernel/execution-modes.md)
:   How Trusted and Sandboxed modes differ.
