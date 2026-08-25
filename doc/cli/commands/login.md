# Login & Install Shortcut

Two small top-level commands, both really about the marketplace rather
than the local xcore runtime.

## `xcli login`

Authorizes this machine with the marketplace via a device-code flow —
opens a browser, you confirm a 6-digit code, `xcli` saves the resulting
credentials on its own. Full walkthrough:
[Authentication → Quick Start](../getting-started/auth.md#quick-start-xcli-login).

```bash
xcli login
```

!!! tip "For CI, not this"
    `xcli login` mints a **personal** credential meant for a human running
    it interactively. CI pipelines should use a project-scoped key and the
    `XCLI_API_KEY`/`XCLI_SIGNING_KEY` environment variables instead — see
    [Environment variables](../getting-started/auth.md#environment-variables).

## `xcli install`

A shortcut for [`xcli plugin install`](../plugin/install.md) — same
command, same options, one less word to type:

```bash
xcli install name-of-plugin
xcli install name-of-plugin@1.2.3
```

There's no equivalent top-level shortcut for service extensions — use
[`xcli service install`](../service/index.md) directly.
