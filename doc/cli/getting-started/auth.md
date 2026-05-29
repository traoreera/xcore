---
title: Authentication
description: Configure credentials to interact with the Xcore marketplace and secure operations.
icon: material/key
---

# Authentication

To interact with the **xcore marketplace** and perform secure operations, you need to configure your credentials.

## Configuration Commands

`xcorecli` provides a `config` command group to manage your local settings.

### Set Authentication Token

Use the `set` command to store your marketplace API key:

```bash title="Configuration"
xcli config set marketplace.api_key "xdk_your-secure-token"
```

!!! warning "Security First"
    Never share your API keys or commit them to version control. `xcorecli` stores these credentials securely in your local environment.

### View Current Configuration

To check your current configuration (with sensitive data masked):

```bash
xcli config show

# Output:
# marketplace.api_key  = xdk_****...****  (set)
# marketplace.url      = https://marketplace.xcorehub.dev
# app.env              = development
```

## Credential Storage

Credentials and sensitive settings are managed by the `xcli/_credentials.py` module, which ensures that:

- API keys are handled securely.
- Tokens are used for marketplace interactions (`marketplace.xcorehub.dev`).
- Sensitive values are masked in all CLI output.

!!! info "Marketplace Integration"
    By default, `xcorecli` connects to `https://marketplace.xcorehub.dev`. You can override this URL in your `integration.yaml` or via the `config` command.

## Environment Variables

For CI/CD pipelines, use environment variables instead of storing credentials locally:

```bash title=".env"
XCORE_MARKETPLACE_API_KEY=xdk_your-token
```

Or export directly in your pipeline:

```bash title="CI/CD example (GitHub Actions)"
env:
  XCORE_MARKETPLACE_API_KEY: ${{ secrets.XCORE_API_KEY }}
```

### Available Environment Variables

| Variable | Description |
|----------|-------------|
| `XCORE_MARKETPLACE_API_KEY` | Marketplace authentication token |
| `XCORE_SECRET_KEY` | Application secret key |
| `XCORE_PLUGINS_KEY` | Plugin signing and verification key |

## Plugin Signing Key

The plugin signing key is separate from the marketplace key. Set it in `integration.yaml` or via an environment variable:

```yaml title="integration.yaml"
plugins:
  secret_key: "${XCORE_PLUGINS_KEY}"
```

```bash
# Sign a plugin using this key
xcli plugin security sign my-plugin --key "${XCORE_PLUGINS_KEY}"
```

## See Also

[Plugin Security](../plugin/security.md)
:   Sign and verify plugins using HMAC signatures.

[Configuration Guide](configuration.md)
:   Full reference for `integration.yaml` settings.
